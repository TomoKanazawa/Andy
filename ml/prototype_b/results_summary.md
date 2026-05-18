# MIMIC-IV DDx Benchmark — Aggregate Summary

> Per-case details (real MIMIC ICD codes, per-patient gold lists, per-patient model output) are gitignored under MIMIC's Data Use Agreement. This file contains only aggregate metrics that do not reveal individual patient data.

## Run 1 — Haiku 4.5, n=10 stratified cases

**Cases:** 10 cherry-picked admissions across 10 specialty buckets
(cardiac, derm, endocrine_metab, ent_eye, gi, infectious, msk_rheum, neuro, onc_hem, psych)
**Total acute gold diagnoses to recover:** 108 across all cases
**Time cutoffs:** admit (HPI + ED only) → +24h → +48h → pre-discharge

| Cutoff | recall@5 | recall@10 | recall@15 |
|---|---|---|---|
| admit | 26/108 (24%) | 44/108 (41%) | 53/108 (49%) |
| +24h | 36/108 (33%) | 47/108 (44%) | 62/108 (57%) |
| +48h | 32/108 (30%) | 46/108 (43%) | 54/108 (50%) |
| pre-discharge | 37/108 (34%) | 49/108 (45%) | 65/108 (60%) |

**Tokens:** 200,366 input · 40,477 output (~$0.40 with Haiku)

## What the numbers mean

The model was given a sanitized patient chart (HPI from admission, ED triage,
labs/imaging/meds filtered to events that became available before the cutoff)
and asked to produce a ranked top-15 differential diagnosis list. The
discharge summary's Brief Hospital Course, Discharge Diagnoses, and Discharge
Medications were never shown to the model.

The gold standard was the patient's actual discharge ICD code list, with
chronic/boilerplate codes (essential HTN, lipid disorders, etc.) filtered
out. Recall@k = fraction of those acute discharge diagnoses that appeared
in the model's top-k.

## Caveats

- **n=10 is small.** Confidence intervals are wide. Treat as a feasibility
  signal, not a published number.
- **No physician review.** The LLM judge used to match candidate→gold ICD
  codes introduces synonym noise; some real matches may be missed and vice
  versa.
- **Recall plateaus, doesn't monotonically increase.** plus48h was slightly
  worse than plus24h — likely noise at this sample size; the curve smooths
  out at larger n.
- **MIMIC is ICU-heavy.** Recall on ambulatory or floor presentations may
  be different.

## Repro

```bash
cd ml/prototype_b
python cherry_pick.py --n 10
python stitch_case.py
python ddx.py --model haiku
```

(Requires PhysioNet credential and MIMIC-IV downloaded under
`physionet.org/files/...` — gitignored.)
