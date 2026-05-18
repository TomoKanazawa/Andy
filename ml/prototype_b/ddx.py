"""Run the LLM DDx benchmark across MIMIC cases at multiple cutoffs.

For each admission in data/<hadm_id>/:
  - For each cutoff (admit / plus24h / plus48h / pre_discharge):
    - Send input.txt to the model, ask for ranked top-15 DDx
    - Score against gold.json's acute_diagnoses
    - Compute recall@5, recall@10, recall@15

Output: results_<model>.md with the recall curve.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

from anthropic import Anthropic
from dotenv import load_dotenv

ROOT = Path(__file__).parent
DATA = ROOT / "data"

MODELS = {
    "haiku": "claude-haiku-4-5",
    "sonnet": "claude-sonnet-4-6",
    "opus": "claude-opus-4-7",
}

CUTOFFS = ["admit", "plus24h", "plus48h", "pre_discharge"]

DDX_PROMPT = """You are a senior internal medicine physician.

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


def extract_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    if start == -1:
        raise ValueError("no JSON object in response")
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


def _call_with_retry(fn, *, max_retries: int = 6, initial_delay: float = 4.0):
    """Retry on OverloadedError / RateLimit / transient API errors."""
    from anthropic import APIError
    delay = initial_delay
    for attempt in range(max_retries):
        try:
            return fn()
        except APIError as e:
            # Catch any anthropic API-side error (overloaded, rate limit, 5xx, etc.)
            if attempt == max_retries - 1:
                raise
            wait = delay * (2 ** attempt)
            print(f"    retry {attempt+1}/{max_retries} after {wait:.0f}s ({type(e).__name__}: {str(e)[:80]})")
            time.sleep(wait)
    raise RuntimeError("unreachable")


def run_ddx(client: Anthropic, model: str, chart: str) -> tuple[list[dict], dict]:
    prompt = DDX_PROMPT.replace("{CHART}", chart)
    def call():
        return client.messages.create(
            model=model,
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}],
        )
    resp = _call_with_retry(call)
    text = resp.content[0].text
    parsed = extract_json(text)
    usage = {
        "input_tokens": resp.usage.input_tokens,
        "output_tokens": resp.usage.output_tokens,
    }
    diff = parsed.get("differential", [])
    return diff, usage


def score_recall(client: Anthropic, judge_model: str,
                 ddx: list[dict], gold: list[dict]) -> dict:
    """One judge call: match each gold dx to a rank in the DDx list (or -1)."""
    n_gold = len(gold)
    if n_gold == 0:
        return {"n_gold": 0, "hits_5": 0, "hits_10": 0, "hits_15": 0,
                "recall_5": 0, "recall_10": 0, "recall_15": 0, "matched_ranks": []}

    gold_list = "\n".join(
        f"  [{i}] {g['icd_code']} — {g['title']}" for i, g in enumerate(gold)
    )
    cand_list = "\n".join(
        f"  Rank {e.get('rank', '?')}: {e.get('diagnosis', '')}" for e in ddx
    )
    prompt = (JUDGE_PROMPT
              .replace("{GOLD_LIST}", gold_list)
              .replace("{CAND_LIST}", cand_list))

    def call():
        return client.messages.create(
            model=judge_model,
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
    resp = _call_with_retry(call)
    try:
        parsed = extract_json(resp.content[0].text)
        matches = parsed.get("matches", [])
    except Exception:
        matches = []

    matched_ranks: list[int | None] = [None] * n_gold
    for m in matches:
        idx = m.get("gold_idx")
        rank = m.get("matched_rank")
        if isinstance(idx, int) and 0 <= idx < n_gold:
            matched_ranks[idx] = rank if (isinstance(rank, int) and rank > 0) else None

    hits_5 = sum(1 for r in matched_ranks if r is not None and r <= 5)
    hits_10 = sum(1 for r in matched_ranks if r is not None and r <= 10)
    hits_15 = sum(1 for r in matched_ranks if r is not None and r <= 15)
    return {
        "n_gold": n_gold,
        "hits_5": hits_5,
        "hits_10": hits_10,
        "hits_15": hits_15,
        "recall_5": hits_5 / n_gold if n_gold else 0,
        "recall_10": hits_10 / n_gold if n_gold else 0,
        "recall_15": hits_15 / n_gold if n_gold else 0,
        "matched_ranks": matched_ranks,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="haiku", choices=list(MODELS.keys()))
    parser.add_argument("--judge", default="haiku", choices=list(MODELS.keys()))
    args = parser.parse_args()

    load_dotenv(ROOT.parent / "prototype_a" / ".env", override=True)
    if not os.getenv("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY not set")

    client = Anthropic()
    model_id = MODELS[args.model]
    judge_id = MODELS[args.judge]

    case_dirs = sorted(d for d in DATA.iterdir() if d.is_dir())
    print(f"Running {len(case_dirs)} cases × {len(CUTOFFS)} cutoffs with {args.model}\n")

    # rows[cutoff][hadm_id] = {ddx, score, gold}
    all_results: dict[str, dict[str, dict]] = {c: {} for c in CUTOFFS}
    in_total = out_total = 0

    for case_dir in case_dirs:
        hadm_id = case_dir.name
        gold_data = json.loads((case_dir / "gold.json").read_text())
        gold_acute = gold_data["acute_diagnoses"]
        print(f"=== {hadm_id} [{gold_data['bucket']}] {len(gold_acute)} acute gold dx ===")

        for cutoff in CUTOFFS:
            chart_path = case_dir / f"{cutoff}.input.txt"
            chart = chart_path.read_text()
            try:
                ddx, usage = run_ddx(client, model_id, chart)
                in_total += usage["input_tokens"]
                out_total += usage["output_tokens"]
            except Exception as e:
                print(f"  {cutoff:<15s} ERROR: {e}")
                all_results[cutoff][hadm_id] = {"error": str(e)}
                continue

            score = score_recall(client, judge_id, ddx, gold_acute)
            print(f"  {cutoff:<15s} "
                  f"r@5={score['hits_5']}/{score['n_gold']} ({score['recall_5']:.0%})  "
                  f"r@10={score['hits_10']}/{score['n_gold']} ({score['recall_10']:.0%})  "
                  f"r@15={score['hits_15']}/{score['n_gold']} ({score['recall_15']:.0%})  "
                  f"in:{usage['input_tokens']} out:{usage['output_tokens']}")

            all_results[cutoff][hadm_id] = {
                "ddx": ddx,
                "score": score,
                "gold_acute": gold_acute,
                "bucket": gold_data["bucket"],
                "primary_dx": gold_data["primary_dx_desc"],
            }

    # Aggregate
    agg = {}
    for cutoff in CUTOFFS:
        rows = [r for r in all_results[cutoff].values() if "score" in r]
        if not rows:
            agg[cutoff] = None
            continue
        total_gold = sum(r["score"]["n_gold"] for r in rows)
        total_5 = sum(r["score"]["hits_5"] for r in rows)
        total_10 = sum(r["score"]["hits_10"] for r in rows)
        total_15 = sum(r["score"]["hits_15"] for r in rows)
        agg[cutoff] = {
            "n_cases": len(rows),
            "total_gold": total_gold,
            "recall_5": total_5 / total_gold if total_gold else 0,
            "recall_10": total_10 / total_gold if total_gold else 0,
            "recall_15": total_15 / total_gold if total_gold else 0,
            "hits_5": total_5,
            "hits_10": total_10,
            "hits_15": total_15,
        }

    # Render markdown
    lines = [f"# MIMIC-IV DDx Benchmark — model: `{args.model}`", ""]
    lines.append(f"**Cases:** {len(case_dirs)} · **Cutoffs:** {', '.join(CUTOFFS)}")
    lines.append(f"**Tokens:** input {in_total:,} · output {out_total:,}")
    lines.append("")
    lines.append("## Recall curve (averaged across all cases, weighted by # of gold dx)")
    lines.append("")
    lines.append("| Cutoff | n_cases | total_gold_dx | recall@5 | recall@10 | recall@15 |")
    lines.append("|---|---|---|---|---|---|")
    for cutoff in CUTOFFS:
        a = agg.get(cutoff)
        if a is None:
            lines.append(f"| {cutoff} | — | — | — | — | — |")
            continue
        lines.append(f"| {cutoff} | {a['n_cases']} | {a['total_gold']} | "
                     f"{a['hits_5']}/{a['total_gold']} ({a['recall_5']:.0%}) | "
                     f"{a['hits_10']}/{a['total_gold']} ({a['recall_10']:.0%}) | "
                     f"{a['hits_15']}/{a['total_gold']} ({a['recall_15']:.0%}) |")

    # Per-case detail
    lines.append("")
    lines.append("## Per-case detail")
    lines.append("")
    for hadm_id in [d.name for d in case_dirs]:
        first_cutoff_data = next((all_results[c].get(hadm_id) for c in CUTOFFS
                                  if "score" in all_results[c].get(hadm_id, {})), None)
        if first_cutoff_data is None:
            continue
        lines.append(f"### {hadm_id} · {first_cutoff_data['bucket']}")
        lines.append(f"**Primary dx:** {first_cutoff_data['primary_dx']}")
        gold = first_cutoff_data["gold_acute"]
        lines.append(f"**Acute gold dx ({len(gold)}):**")
        for g in gold[:15]:
            lines.append(f"  - {g['icd_code']} — {g['title']}")
        lines.append("")
        lines.append("| Cutoff | r@5 | r@10 | r@15 |")
        lines.append("|---|---|---|---|")
        for cutoff in CUTOFFS:
            r = all_results[cutoff].get(hadm_id, {})
            if "score" not in r:
                lines.append(f"| {cutoff} | — | — | — |")
                continue
            s = r["score"]
            lines.append(f"| {cutoff} | {s['hits_5']}/{s['n_gold']} | {s['hits_10']}/{s['n_gold']} | {s['hits_15']}/{s['n_gold']} |")
        lines.append("")

    out_path = ROOT / f"results_{args.model}.md"
    out_path.write_text("\n".join(lines))

    # Per-case JSON for inspection
    json_out = ROOT / f"results_{args.model}.json"
    json_out.write_text(json.dumps({
        "model": args.model,
        "in_tokens": in_total,
        "out_tokens": out_total,
        "agg": agg,
        "per_case": all_results,
    }, indent=2, default=str))

    print(f"\n=== AGGREGATE ===")
    for cutoff in CUTOFFS:
        a = agg.get(cutoff)
        if a:
            print(f"  {cutoff:<15s} "
                  f"recall@5: {a['recall_5']:.0%}  "
                  f"recall@10: {a['recall_10']:.0%}  "
                  f"recall@15: {a['recall_15']:.0%}")

    print(f"\nTotal tokens: in={in_total:,}  out={out_total:,}")
    print(f"Results: {out_path}")


if __name__ == "__main__":
    main()
