"""Two-pass DDx: ask for top 15, then ask "what else?" for ranks 16-30.

Tests whether a second pass asking the LLM to find additional diagnoses
it may have missed actually increases recall.

Reuses the chart input files and gold.json files produced by stitch_case.py.
Compares recall@15 (first pass only) vs recall@30 (first + second pass combined).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

from anthropic import APIError, Anthropic
from dotenv import load_dotenv

ROOT = Path(__file__).parent
DATA = ROOT / "data"

MODELS = {
    "haiku": "claude-haiku-4-5",
    "sonnet": "claude-sonnet-4-6",
    "opus": "claude-opus-4-7",
}

CUTOFFS = ["admit", "plus24h", "plus48h", "pre_discharge"]

# High-stakes prefixes (copied from ddx.py — we don't import to keep self-contained)
HIGH_STAKES_ICD10 = [
    "A40", "A41", "B37", "C", "D62", "D63", "D69", "E87",
    "G93", "F05", "I21", "I22", "I26", "I46", "I50", "I63",
    "I61", "J12", "J13", "J14", "J15", "J16", "J17", "J18",
    "J93", "J96", "K56", "K70", "K72", "K85", "K92", "N17",
    "N39", "R57",
]
HIGH_STAKES_ICD9 = [
    "038", "584", "428", "410", "411", "415", "433", "434",
    "431", "480", "481", "482", "483", "484", "485", "486",
    "507", "518", "578", "577", "572.2", "293", "348", "042",
    "112", "250.1", "250.2", "260", "261", "262", "263",
    "276", "278", "285", "286", "287", "288",
]
HIGH_STAKES_ICD9 += [str(c) for c in range(140, 210)]


def is_high_stakes(icd_code: str, version: int) -> bool:
    code = str(icd_code).strip()
    if not code:
        return False
    table = HIGH_STAKES_ICD9 if version == 9 else HIGH_STAKES_ICD10
    return any(code.startswith(p) for p in table)


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

PASS1_PROMPT = """You are a senior internal medicine physician.

Below is a patient chart, including admission notes, exam, and any available labs/imaging/medications up to a specified cutoff time.

Your task: produce a ranked list of the TOP 15 most likely diagnoses that this patient has (or will be found to have) during this hospitalization. Include:
- The principal/primary admitting diagnosis (most likely cause for hospitalization)
- Any secondary acute diagnoses that the workup suggests or that you would expect to be confirmed during the stay (e.g., AKI, electrolyte derangements, complications)

Return STRICT JSON only, no prose:

{
  "differential": [
    {"rank": 1, "diagnosis": "...", "reasoning": "one short sentence"},
    {"rank": 2, "diagnosis": "...", "reasoning": "..."},
    ...
    {"rank": 15, "diagnosis": "...", "reasoning": "..."}
  ]
}

Be specific (e.g., "septic shock due to UTI" not just "infection"). Use standard medical terminology that would map to ICD codes.

CHART:
---
{CHART}
---
"""

PASS2_PROMPT = """You previously generated a top-15 ranked differential diagnosis for the patient chart below.

PREVIOUS TOP 15:
{PREV_LIST}

Now look at the chart again with fresh eyes. What additional acute diagnoses might be present that your top 15 did not cover?

Look specifically for:
- Conditions implied by ordered medications (laxatives → constipation; antipsychotics → psych dx; insulin → diabetic complication; vasopressors → shock; benzos+thiamine → alcohol withdrawal)
- Lab abnormalities you haven't yet named as their specific condition (specific electrolytes by name; cytopenias combined into pancytopenia; rising creatinine → AKI)
- Imaging findings mentioned in radiology reports that you didn't list (mass, varices, effusion, hematoma, ascites, free air, consolidation)
- Conditions mentioned in PMH that may be active during this admission (e.g., known malignancy, prior MI, peripheral vascular disease)
- Subtle complications (constipation, hypotension, mild thrombocytopenia, vitamin deficiency)

Return up to 15 additional ranked diagnoses (ranks 16-30). DO NOT repeat any from the previous list. If fewer than 15 additional are warranted, return as many as are clinically supported.

STRICT JSON only:

{
  "additional": [
    {"rank": 16, "diagnosis": "...", "reasoning": "specific chart evidence"},
    ...
  ]
}

CHART:
---
{CHART}
---
"""

JUDGE_PROMPT = """You match each gold diagnosis to the first clinically equivalent candidate in a ranked differential diagnosis list.

GOLD diagnoses (the patient's actual final diagnoses):
{GOLD_LIST}

CANDIDATE ranked DDx (the LLM's predictions, ordered most-to-least likely):
{CAND_LIST}

For EACH gold diagnosis, find the rank of the FIRST candidate that clinically refers to the same condition (same ICD root, same disease, or candidate is a more-specific form). Use -1 if no candidate matches.

Be reasonably lenient on synonyms but strict on different organ systems / different mechanisms. "Sepsis" matches "septicemia" or "septic shock from X." "AKI" matches "acute renal failure." "Heart failure" does NOT match "ischemic heart disease."

Return STRICT JSON only:
{"matches": [{"gold_idx": 0, "matched_rank": 3}, {"gold_idx": 1, "matched_rank": -1}, ...]}
"""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def call_with_retry(client, fn, max_retries=6, initial_delay=4.0):
    delay = initial_delay
    for attempt in range(max_retries):
        try:
            return fn()
        except APIError as e:
            if attempt == max_retries - 1:
                raise
            wait = delay * (2 ** attempt)
            print(f"    retry after {wait:.0f}s ({type(e).__name__})")
            time.sleep(wait)


def extract_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    if start == -1:
        raise ValueError("no JSON")
    depth = 0
    end = -1
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    block = text[start:end] if end > 0 else text[start:]
    try:
        return json.loads(block)
    except json.JSONDecodeError:
        block = re.sub(r",(\s*[}\]])", r"\1", block)
        return json.loads(block)


def run_pass1(client, model, chart):
    prompt = PASS1_PROMPT.replace("{CHART}", chart)
    def call():
        return client.messages.create(model=model, max_tokens=4000,
                                       messages=[{"role": "user", "content": prompt}])
    resp = call_with_retry(client, call)
    parsed = extract_json(resp.content[0].text)
    return parsed.get("differential", []), {
        "input_tokens": resp.usage.input_tokens,
        "output_tokens": resp.usage.output_tokens,
    }


def run_pass2(client, model, chart, prev_ddx):
    prev_list = "\n".join(f"  {e.get('rank')}. {e.get('diagnosis', '')}" for e in prev_ddx)
    prompt = PASS2_PROMPT.replace("{CHART}", chart).replace("{PREV_LIST}", prev_list)
    def call():
        return client.messages.create(model=model, max_tokens=4000,
                                       messages=[{"role": "user", "content": prompt}])
    resp = call_with_retry(client, call)
    parsed = extract_json(resp.content[0].text)
    return parsed.get("additional", []), {
        "input_tokens": resp.usage.input_tokens,
        "output_tokens": resp.usage.output_tokens,
    }


def score(client, judge_model, ddx, gold):
    n_gold = len(gold)
    if n_gold == 0:
        return None
    gold_list = "\n".join(f"  [{i}] {g['icd_code']} — {g['title']}" for i, g in enumerate(gold))
    cand_list = "\n".join(f"  Rank {e.get('rank', '?')}: {e.get('diagnosis', '')}" for e in ddx)
    prompt = (JUDGE_PROMPT.replace("{GOLD_LIST}", gold_list).replace("{CAND_LIST}", cand_list))
    def call():
        return client.messages.create(model=judge_model, max_tokens=2500,
                                       messages=[{"role": "user", "content": prompt}])
    resp = call_with_retry(client, call)
    try:
        parsed = extract_json(resp.content[0].text)
        matches = parsed.get("matches", [])
    except Exception:
        matches = []

    matched_ranks = [None] * n_gold
    for m in matches:
        idx = m.get("gold_idx")
        rank = m.get("matched_rank")
        if isinstance(idx, int) and 0 <= idx < n_gold:
            matched_ranks[idx] = rank if (isinstance(rank, int) and rank > 0) else None

    hs_flags = [is_high_stakes(g["icd_code"], g["icd_version"]) for g in gold]

    def hits(k, subset=None):
        if subset is None:
            subset = [True] * n_gold
        return sum(1 for r, s in zip(matched_ranks, subset) if s and r is not None and r <= k)

    n_hs = sum(hs_flags)
    return {
        "n_gold": n_gold,
        "n_high_stakes": n_hs,
        "hits_15": hits(15),
        "hits_30": hits(30),
        "hits_hs_15": hits(15, hs_flags),
        "hits_hs_30": hits(30, hs_flags),
        "matched_ranks": matched_ranks,
        "high_stakes_flags": hs_flags,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="haiku", choices=list(MODELS.keys()))
    parser.add_argument("--judge", default="haiku", choices=list(MODELS.keys()))
    parser.add_argument("--n", type=int, default=10,
                        help="Number of cases to test (first N alphabetically). Default 10.")
    args = parser.parse_args()

    load_dotenv(ROOT.parent / "prototype_a" / ".env", override=True)
    if not os.getenv("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY not set")

    client = Anthropic()
    model_id = MODELS[args.model]
    judge_id = MODELS[args.judge]

    case_dirs = sorted(d for d in DATA.iterdir() if d.is_dir())[:args.n]
    print(f"Two-pass DDx: {len(case_dirs)} cases × {len(CUTOFFS)} cutoffs with {args.model}\n")

    results = {c: {} for c in CUTOFFS}
    in_total = out_total = 0

    for case_dir in case_dirs:
        hadm_id = case_dir.name
        gold = json.loads((case_dir / "gold.json").read_text())["acute_diagnoses"]
        print(f"=== {hadm_id}  n_gold={len(gold)} ===")

        for cutoff in CUTOFFS:
            chart = (case_dir / f"{cutoff}.input.txt").read_text()
            try:
                ddx1, usage1 = run_pass1(client, model_id, chart)
                in_total += usage1["input_tokens"]; out_total += usage1["output_tokens"]
                # Score pass 1 alone
                score1 = score(client, judge_id, ddx1, gold)
                # Pass 2: ask for additional dx
                ddx2_extra, usage2 = run_pass2(client, model_id, chart, ddx1)
                in_total += usage2["input_tokens"]; out_total += usage2["output_tokens"]
                # Combine pass 1 (ranks 1-15) + pass 2 (ranks 16-30)
                combined = list(ddx1) + list(ddx2_extra)
                score_combined = score(client, judge_id, combined, gold)
            except Exception as e:
                print(f"  {cutoff:<15s} ERROR: {e}")
                results[cutoff][hadm_id] = {"error": str(e)}
                continue

            print(f"  {cutoff:<15s} "
                  f"P1 r@15={score1['hits_15']}/{score1['n_gold']} hs={score1['hits_hs_15']}/{score1['n_high_stakes']}  "
                  f"→  P1+P2 r@30={score_combined['hits_30']}/{score_combined['n_gold']} hs={score_combined['hits_hs_30']}/{score_combined['n_high_stakes']}  "
                  f"(added {len(ddx2_extra)} dx)")

            results[cutoff][hadm_id] = {
                "ddx_pass1": ddx1,
                "ddx_pass2_extra": ddx2_extra,
                "ddx_combined": combined,
                "score_pass1": score1,
                "score_combined": score_combined,
                "gold": gold,
            }

    # Aggregate
    print("\n=== AGGREGATE (10 cases) ===")
    print(f"{'Cutoff':<15s}  {'P1 r@15':>10s}  {'P1 hs@15':>10s}  {'P1+P2 r@30':>10s}  {'P1+P2 hs@30':>10s}  {'Δ hs (pp)':>10s}")
    for cutoff in CUTOFFS:
        rows = [r for r in results[cutoff].values() if "score_pass1" in r]
        if not rows:
            continue
        total_gold = sum(r["score_pass1"]["n_gold"] for r in rows)
        total_hs = sum(r["score_pass1"]["n_high_stakes"] for r in rows)
        hits15 = sum(r["score_pass1"]["hits_15"] for r in rows)
        hits_hs15 = sum(r["score_pass1"]["hits_hs_15"] for r in rows)
        hits30 = sum(r["score_combined"]["hits_30"] for r in rows)
        hits_hs30 = sum(r["score_combined"]["hits_hs_30"] for r in rows)
        delta = (hits_hs30 - hits_hs15) / total_hs * 100 if total_hs else 0
        print(f"  {cutoff:<13s}  "
              f"{hits15}/{total_gold} ({hits15/total_gold:.0%})  "
              f"{hits_hs15}/{total_hs} ({hits_hs15/total_hs:.0%})  "
              f"{hits30}/{total_gold} ({hits30/total_gold:.0%})  "
              f"{hits_hs30}/{total_hs} ({hits_hs30/total_hs:.0%})  "
              f"+{delta:.0f}pp")

    print(f"\nTokens: in={in_total:,}  out={out_total:,}")

    out_path = ROOT / f"results_twopass_{args.model}.json"
    out_path.write_text(json.dumps(results, indent=2, default=str))
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    main()
