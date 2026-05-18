"""Select diagnostically interesting MIMIC-IV admissions for the DDx benchmark.

Filters:
  - Adult (age >= 18)
  - Admitted via ED-route (undifferentiated presentation)
  - LOS between 1 and 14 days (real workup happened, not too many post-admission
    complications that the LLM couldn't predict at admission time)
  - Survived first 24h (so workup actually happened)
  - >=2 non-chronic discharge diagnoses (real diagnostic puzzle, not just
    "essential HTN maintained")

Output: selected_admissions.json — list of (hadm_id, subject_id, metadata).
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[2]
HOSP = ROOT / "physionet.org" / "files" / "mimiciv" / "3.1" / "hosp"
OUT = Path(__file__).parent / "selected_admissions.json"

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

ED_ADMISSION_TYPES = {
    "EW EMER.",
    "URGENT",
    "OBSERVATION ADMIT",
    "DIRECT EMER.",
    "EU OBSERVATION",
    "DIRECT OBSERVATION",
}

LOS_MIN_DAYS = 1
LOS_MAX_DAYS = 14
MIN_ACUTE_DX = 2

# ICD prefixes for chronic / status / boilerplate codes that should NOT count
# as "acute diagnoses for this admission." Generous prefix list.
CHRONIC_ICD_PATTERNS = re.compile(
    r"^("
    r"I10"       # Essential HTN
    r"|I11|I12|I13|I15"  # Other HTN
    r"|E78"      # Lipid disorders
    r"|E11"      # Type 2 DM (unless complicating, often background)
    r"|E03"      # Hypothyroidism background
    r"|E66"      # Obesity
    r"|Z"        # Status of / history of / encounter for
    r"|F17"      # Tobacco use
    r"|F32|F33"  # Depression (background usually)
    r"|F41"      # Anxiety (background)
    r"|N18"      # CKD background (unless ESRD with crisis)
    r"|G47"      # Sleep disorders
    r"|H"        # Eye / ear (usually incidental)
    r"|M81"      # Osteoporosis
    r"|K21"      # GERD
    r")"
)

# Map first letter of ICD10 → diagnostic bucket
ICD10_BUCKETS = {
    "A": "infectious", "B": "infectious",
    "C": "onc_hem", "D": "onc_hem",
    "E": "endocrine_metab",
    "F": "psych",
    "G": "neuro",
    "H": "ent_eye",
    "I": "cardiac",
    "J": "pulm",
    "K": "gi",
    "L": "derm",
    "M": "msk_rheum",
    "N": "renal_gu",
    "O": "ob",
    "P": "perinatal",
    "Q": "congenital",
    "R": "symptoms_ill_defined",
    "S": "injury_trauma", "T": "injury_trauma",
    "U": "other",
    "V": "external", "W": "external", "X": "external", "Y": "external",
    "Z": "status",
}


def icd9_bucket(code: str) -> str:
    """Map an ICD-9 numeric code (or V/E prefix) to a bucket."""
    code = code.strip()
    if not code:
        return "unknown"
    # V codes and E codes
    if code[0].upper() == "V":
        return "status"
    if code[0].upper() == "E":
        return "external"
    # Numeric — take first 3 digits
    try:
        n = int(code.split(".")[0])
    except ValueError:
        return "other"
    if 1 <= n <= 139:
        return "infectious"
    if 140 <= n <= 239:
        return "onc_hem"
    if 240 <= n <= 279:
        return "endocrine_metab"
    if 280 <= n <= 289:
        return "onc_hem"
    if 290 <= n <= 319:
        return "psych"
    if 320 <= n <= 359:
        return "neuro"
    if 360 <= n <= 389:
        return "ent_eye"
    if 390 <= n <= 459:
        return "cardiac"
    if 460 <= n <= 519:
        return "pulm"
    if 520 <= n <= 579:
        return "gi"
    if 580 <= n <= 629:
        return "renal_gu"
    if 630 <= n <= 679:
        return "ob"
    if 680 <= n <= 709:
        return "derm"
    if 710 <= n <= 739:
        return "msk_rheum"
    if 740 <= n <= 759:
        return "congenital"
    if 760 <= n <= 779:
        return "perinatal"
    if 780 <= n <= 799:
        return "symptoms_ill_defined"
    if 800 <= n <= 999:
        return "injury_trauma"
    return "other"


def bucket_for(icd: str) -> str:
    if not icd:
        return "unknown"
    first = icd[0].upper()
    # If it starts with a letter and looks like ICD-10 (letter + digit), use ICD-10 map
    if first.isalpha() and first not in {"V", "E"}:
        return ICD10_BUCKETS.get(first, "other")
    # Otherwise treat as ICD-9
    return icd9_bucket(icd)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Cherry-pick MIMIC-IV admissions for DDx benchmark.")
    parser.add_argument("--n", type=int, default=None,
                        help="If set, stratified-sample this many admissions across buckets.")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for stratified sampling.")
    parser.add_argument("--exclude-buckets", nargs="*", default=["other", "unknown", "status", "external", "perinatal", "congenital", "ob", "injury_trauma"],
                        help="Buckets to exclude from stratified sampling.")
    args = parser.parse_args()

    print(f"Loading from {HOSP}")

    # 1. Patients
    print("[1/5] patients.csv.gz")
    patients = pd.read_csv(HOSP / "patients.csv.gz", usecols=["subject_id", "anchor_age", "gender", "dod"])
    print(f"    {len(patients):,} patients")

    # 2. Admissions
    print("[2/5] admissions.csv.gz")
    adm = pd.read_csv(
        HOSP / "admissions.csv.gz",
        usecols=[
            "subject_id", "hadm_id", "admittime", "dischtime", "deathtime",
            "admission_type", "admission_location", "discharge_location",
            "race", "edregtime",
        ],
        parse_dates=["admittime", "dischtime", "deathtime"],
    )
    print(f"    {len(adm):,} admissions (raw)")

    # Filter: ED-route admissions
    adm = adm[adm["admission_type"].isin(ED_ADMISSION_TYPES)].copy()
    print(f"    {len(adm):,} after admission_type filter")

    # Filter: LOS
    adm["los_days"] = (adm["dischtime"] - adm["admittime"]).dt.total_seconds() / 86400
    adm = adm[(adm["los_days"] >= LOS_MIN_DAYS) & (adm["los_days"] <= LOS_MAX_DAYS)]
    print(f"    {len(adm):,} after LOS {LOS_MIN_DAYS}-{LOS_MAX_DAYS} day filter")

    # Filter: survived first 24h
    adm["died_early"] = (
        adm["deathtime"].notna()
        & (adm["deathtime"] <= adm["admittime"] + pd.Timedelta(hours=24))
    )
    adm = adm[~adm["died_early"]]
    print(f"    {len(adm):,} after early-death filter")

    # Join age
    adm = adm.merge(patients[["subject_id", "anchor_age", "gender"]], on="subject_id", how="left")
    adm = adm[adm["anchor_age"] >= 18]
    print(f"    {len(adm):,} after adult filter")

    # 3. Diagnoses
    print("[3/5] diagnoses_icd.csv.gz")
    dx = pd.read_csv(
        HOSP / "diagnoses_icd.csv.gz",
        dtype={"subject_id": "int64", "hadm_id": "int64", "seq_num": "int64",
               "icd_code": "str", "icd_version": "int64"},
    )
    print(f"    {len(dx):,} dx rows")

    # Drop chronic / boilerplate codes
    dx["is_chronic"] = dx["icd_code"].astype(str).str.match(CHRONIC_ICD_PATTERNS)
    acute = dx[~dx["is_chronic"]]
    print(f"    {len(acute):,} acute dx rows after chronic filter")

    # Count acute dx per admission
    n_acute = acute.groupby("hadm_id").size().rename("n_acute_dx").reset_index()
    adm = adm.merge(n_acute, on="hadm_id", how="left").fillna({"n_acute_dx": 0})
    adm["n_acute_dx"] = adm["n_acute_dx"].astype(int)
    adm = adm[adm["n_acute_dx"] >= MIN_ACUTE_DX]
    print(f"    {len(adm):,} admissions with >={MIN_ACUTE_DX} acute dx")

    # 4. Primary acute dx for each admission (lowest seq_num among non-chronic)
    print("[4/5] picking primary acute dx per admission")
    primary = (
        acute.sort_values(["hadm_id", "seq_num"])
        .groupby("hadm_id")
        .first()
        .reset_index()[["hadm_id", "icd_code"]]
        .rename(columns={"icd_code": "primary_dx_icd"})
    )
    adm = adm.merge(primary, on="hadm_id", how="left")
    # Load icd dictionary for description
    icd_dict = pd.read_csv(HOSP / "d_icd_diagnoses.csv.gz", usecols=["icd_code", "long_title"])
    icd_dict = icd_dict.drop_duplicates("icd_code")
    adm = adm.merge(icd_dict, left_on="primary_dx_icd", right_on="icd_code", how="left")
    adm = adm.rename(columns={"long_title": "primary_dx_desc"}).drop(columns=["icd_code"], errors="ignore")
    adm["bucket"] = adm["primary_dx_icd"].fillna("").map(bucket_for)

    # 5. Stratified sample if --n requested
    if args.n is not None:
        eligible = adm[~adm["bucket"].isin(args.exclude_buckets)].copy()
        buckets_present = sorted(eligible["bucket"].unique())
        per_bucket = max(1, args.n // len(buckets_present))
        print(f"\n[5/5] stratified sample: ~{per_bucket} per bucket × {len(buckets_present)} buckets")

        sampled_parts = []
        for b in buckets_present:
            grp = eligible[eligible["bucket"] == b]
            take = min(per_bucket, len(grp))
            sampled_parts.append(grp.sample(n=take, random_state=args.seed))
        sampled = pd.concat(sampled_parts)
        # If we are short of n (uneven division), top up from remaining pool
        if len(sampled) < args.n:
            remaining = eligible.drop(sampled.index)
            shortfall = args.n - len(sampled)
            sampled = pd.concat([sampled, remaining.sample(n=min(shortfall, len(remaining)), random_state=args.seed)])
        # If over, trim
        sampled = sampled.head(args.n).reset_index(drop=True)
        adm = sampled
        print(f"    sampled {len(adm)} admissions")

    # Output
    print(f"\nWriting {len(adm)} admissions")
    out_rows = []
    for _, r in adm.iterrows():
        out_rows.append({
            "hadm_id": int(r["hadm_id"]),
            "subject_id": int(r["subject_id"]),
            "admittime": str(r["admittime"]),
            "dischtime": str(r["dischtime"]),
            "los_days": round(float(r["los_days"]), 1),
            "age": int(r["anchor_age"]),
            "gender": r["gender"],
            "admission_type": r["admission_type"],
            "primary_dx_icd": r.get("primary_dx_icd") or "",
            "primary_dx_desc": (r.get("primary_dx_desc") or "")[:120],
            "bucket": r["bucket"],
            "n_acute_dx": int(r["n_acute_dx"]),
        })

    OUT.write_text(json.dumps(out_rows, indent=2))
    print(f"\n✓ {len(out_rows):,} candidate admissions written to {OUT}")

    # Bucket breakdown
    bucket_counts = adm["bucket"].value_counts().to_dict()
    print("\nBucket breakdown:")
    for b, c in sorted(bucket_counts.items(), key=lambda x: -x[1]):
        print(f"  {b:<25s} {c:>6,}")

    if args.n is not None:
        print("\nSelected admissions (sample):")
        for r in out_rows[:20]:
            print(f"  hadm_id={r['hadm_id']:>10}  los={r['los_days']:>5}d  "
                  f"[{r['bucket']:<25s}]  {r['primary_dx_desc'][:60]}")


if __name__ == "__main__":
    main()
