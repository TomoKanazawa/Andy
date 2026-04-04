# Temporal Patient Truth Layer — Product Context for Development

## What This Document Is

This is the complete product context derived from 30+ rounds of deep market research, competitive analysis, and product design decisions. Use this to understand what we're building, why, for whom, and how it fits into the existing healthcare ecosystem. Technical specifications are covered separately.

---

## The Product in One Paragraph

A single-page, problem-oriented "Current Truth" view of a patient that lives inside Epic EHR as an embedded panel. It reads all patient data (structured lists, clinical notes, labs, encounters), understands which information supersedes which using temporal reasoning, detects contradictions between sources, and surfaces what changed since the doctor last saw the patient. Every claim is linked to its source document, author, and date. It replaces the doctor's current 5–14 minute scavenger hunt across 6+ screens with a 2-minute scan of one organized page.

---

## The Problem

### What doctors do today

Doctors use **Epic Hyperspace** (desktop app) or **Epic Hyperdrive** (newer Chromium-based app) as their primary clinical interface. When reviewing a patient's chart before or during a visit, they navigate across an average of **6.3 different screens** per patient — results review, summary/overview, flowsheet, chart review tab, notes, medications.

Key pain statistics:
- **5.4 minutes per encounter** spent on chart review (33% of total EHR time)
- **70% of physicians** report difficulty finding information in the EHR
- **50% of clinical note text** is copy-pasted from prior visits; only 18% is original
- Average patient chart contains **359 clinical notes** (up from 5 in 2006)
- Problem lists have **8–46% sensitivity** for major conditions (wildly inaccurate)
- Medication lists are accurate only **21.9% of the time**
- In the ICU, trainees **miss 22% of lab data** and **misrepresent 39%** during rounds
- A patient was documented as "postoperative day 2" for **5.5 consecutive weeks** due to copy-paste propagation

### Why existing tools don't solve this

| Tool | What it does | What it doesn't do |
|------|-------------|-------------------|
| **Epic's native views** | Shows raw data across tabs | No intelligence, no reconciliation, no temporal awareness |
| **Epic Art** (AI assistant) | Chat interface over charts, generates summaries | Solves comprehension (15-20% of friction), not finding (60-80%) |
| **Navina** ($100M raised, Best in KLAS) | Generates per-visit Patient Portrait from multi-source data | Ephemeral (regenerated each visit, not persistent), no temporal supersession, no contradiction detection, focused on VBC/risk adjustment |
| **Zus Health** ($74M raised) | Aggregates patient data across networks, deduplicates by code | "Most recent date wins" (mechanical, not clinical), no contradiction resolution, sells to digital health startups not health systems |
| **Regard** ($82M raised, 150+ hospitals) | Detects missed diagnoses, generates documentation | Not a truth layer — outputs diagnosis suggestions, doesn't track current patient state |
| **Pieces Technologies** | Had 2-minute continuous updates | Acquired into revenue cycle company (SmarterNotes), no longer independent |

### The core insight

**60–80% of chart review friction is finding and navigating** (clicking between screens, scrolling through hundreds of notes, filtering through copy-pasted content). Only 15–20% is comprehension (reading and understanding once found). Epic Art and most AI tools attack comprehension. Nobody attacks the finding problem with temporal intelligence.

---

## What We're Building

### The five capabilities that define this product

1. **Temporal supersession** — Knows that a cardiologist's January note overrides a PCP's September note on the same diagnosis. Not just "most recent date wins" but clinically-informed reasoning about which source should take precedence.

2. **Contradiction detection** — When the medication list says metformin but the latest note says "discontinued metformin," this is flagged explicitly rather than silently ignored.

3. **Persistent truth layer** — Continuously maintained between visits, not regenerated on-demand. The patient's truth state is always current, not a point-in-time snapshot.

4. **"What changed since last visit"** — First-class feature. Doctor opens the view and immediately sees what's new, what's different, what contradicts their last understanding of this patient.

5. **Source provenance on every claim** — Every fact shows who documented it, when, in what context. Physicians explicitly distrust systems that hide sources (Vanderbilt study: provenance was the #1 trust signal).

### What the doctor sees

A single page organized by **active problem**. Each problem is a row or card showing:
- Current status
- When it was last confirmed
- Who confirmed it
- Whether it changed since the doctor last saw this patient
- Visual confidence indicator (green = multiple recent sources agree, yellow = stale or single-source, red = contradiction detected)

Clicking any problem expands into the **full evidence chain**: every note, lab, specialist opinion that informs the current understanding of that problem, arranged chronologically with source attribution.

### What it is NOT

- NOT a chat interface over the chart (that's Epic Art)
- NOT a missed diagnosis detector (that's Regard)
- NOT an ambient documentation tool (that's Abridge)
- NOT a data aggregation platform (that's Zus Health)
- NOT a point-in-time summary (that's Navina)
- NOT a clinical decision support tool making treatment recommendations

It is the **document that should exist but doesn't** — the continuously-maintained, temporally-aware current truth about each patient.

---

## How It Lives Inside Epic

### Integration mechanism

The app renders as an **embedded panel or tab within Epic** using the **SMART on FHIR** standard. Epic opens an iframe inside its interface; our web app renders there. To the doctor, it looks like part of Epic.

How it works technically:
1. Doctor opens a patient chart in Epic
2. Clicks our app's button (configured by the hospital's IT team)
3. Epic sends our app the patient ID + authentication token via SMART on FHIR
4. Our app calls Epic's FHIR APIs to pull patient data (and/or retrieves from our persistent backend store)
5. Our app renders the "current truth" page inside that iframe

### What this means for the UI

- It is a **web application** (React frontend) rendered inside Epic's application frame
- Epic Hyperspace = Windows desktop app (legacy, most hospitals today)
- Epic Hyperdrive = Chromium-based app (the future, actively migrating)
- In both cases, our app appears as a panel/tab alongside Epic's native content — not a popup, not a separate window
- The hospital's IT team controls **where** our app appears (which tab, how prominent)
- We do NOT need Epic corporate's permission to integrate — we need each **hospital's** IT team to configure access
- Listing on Epic's App Showroom (optional, requires Epic review) helps scale but is not required to operate

### Push vs. pull

The proven pattern from successful AI startups (Navina at 86% adoption, Regard at 150+ hospitals) is:
- **Primary mode: Pull** — doctor opens the view before seeing the patient (pre-visit prep)
- **Secondary mode: Push** — a single badge/card via CDS Hooks when the patient's truth state has materially changed (new hospitalization, contradictory diagnosis). NOT pop-up alerts (96% override rate, alert fatigue is severe)

---

## The Market

### Who buys this

**Primary target: Value-based care organizations and large primary care groups**
- CMIOs (Chief Medical Information Officers) and VPs of Population Health
- Same buyer profile as Navina's existing customers
- VBC incentives align (better data → better risk adjustment → more revenue)

**Entry wedge: Primary care pre-visit preparation**
- Highest aggregate chart review volume
- Longest patient relationships requiring longitudinal tracking
- "What changed since last visit" is the most natural fit
- VBC revenue framing (missed HCC codes, RAF score improvement)

**Expansion paths:**
- ICU (trajectory detection: is this patient getting better or worse?)
- Emergency department (rapid distillation of unknown patients)
- Specialty care (oncology, complex chronic disease management)

### Market validation

- **400+ hospitals** have purchased chart review / clinical workflow tools from third parties
- KLAS created a formal category: **"Clinician Digital Workflow"**
- **57% of health system C-suites** rank AI clinical solutions as #1 tech initiative (up from 19% in 2023)
- **$275M+ in combined VC** invested in chart review tools (Regard, Navina, TransformativeMed, Pieces)
- Navina achieves **86% weekly active usage** and **61% chart review time reduction**
- Regard demonstrates **$4.4M annual revenue uplift** at a single health system through better diagnosis capture

### How to frame the ROI

Do NOT sell this as "data quality" or "temporal truth" — hospitals don't buy that category. Sell it as:
- **Missed diagnosis capture** → revenue from correct risk coding
- **RAF score improvement** → higher VBC contract payments
- **Chart review time reduction** → physician capacity and throughput
- **Reduced adverse events** → from stale medication lists and outdated problem lists
- **Physician satisfaction/retention** → reducing burnout-driven turnover

---

## Competitive Landscape

### Direct competitors (none exact, several adjacent)

| Company | Funding | What they do | Gap vs. our product |
|---------|---------|-------------|-------------------|
| **Navina** | $100M | Per-visit Patient Portrait using knowledge graph | Ephemeral (not persistent), no formal temporal supersession, no contradiction detection, VBC-focused only |
| **Zus Health** | $74M | FHIR data aggregation + deduplication across networks | "Most recent date wins" (mechanical), no clinical reasoning, sells to digital health startups not health systems |
| **Regard** | $82M | Missed diagnosis detection + documentation | Not a truth layer — outputs diagnosis suggestions, doesn't maintain patient state |
| **Layer Health** | $21M | LLM-based longitudinal chart reasoning | Very early, MIT-founded, potentially closest but unclear product |
| **Mendel AI** | $40M+ | Clinical hypergraph for "lifelong medical journey" | Life sciences focus, not point-of-care delivery |
| **Epic Art** | Native | AI chat/summaries over patient charts | Comprehension tool, not temporal truth layer. "Since last seen" summaries exist but lack formal supersession or contradiction detection |

### The existential threat: Epic

Epic is the #1 risk. Key facts:
- **42% of US acute care hospitals**, 325M patient records
- Art already does **16M+ summary requests/month**
- Cosmos model trained on **300M patients, 8B+ encounters**
- Agent Factory (announced HIMSS 2026) enables custom AI agents
- Pattern: partner → learn → build → compete (ambient scribes are the live cautionary tale — Epic shipped native scribe 6 months after announcement, third-party vendors already failing)
- **Estimated window: 2–3 years** before Epic builds "good enough" native temporal intelligence

### Why the window exists

- Epic's Art solves **comprehension** (chat over charts). Our product solves **finding** (temporal truth). Different problems.
- Temporal supersession logic is genuinely hard — nobody has solved it, including Epic
- The Cures Act legally protects third-party FHIR read access ($1M/violation penalties)
- 3 active antitrust lawsuits against Epic create regulatory pressure for openness
- Regard proves the read-heavy-from-Epic third-party model works at 150+ hospitals

---

## What Doctors Want (Research-Backed Design Principles)

From the Vanderbilt ethnographic study (732 coded excerpts, 13 clinicians):

1. **Abstraction over filtration** (240 mentions) — Compress detail without hiding it. Layered summary with drill-down. Doctors explicitly distrust systems that filter/hide data. They'd rather see everything compressed than have an AI decide what's important.

2. **Provenance** (78 of 175 reliability mentions) — Who said this, when, does it contradict something else? This is the #1 trust signal. Every claim must be traceable to its source.

3. **Data age** (32 reliability mentions) — Is this current or from 3 years ago? Visual indicators of freshness/staleness.

4. **Problem-oriented + temporal organization** — Doctors think in problems/systems (the Assessment & Plan structure) but need temporal context within each problem. Organize by problem, show what changed within each.

5. **Show contradictions, don't resolve them** — Doctors want to see conflicting information and resolve it themselves. Don't be an oracle that declares truth — be an assistant that surfaces the evidence.

### Trust architecture (critical)

- **Every claim must link to source** — following Abridge's "Linked Evidence" model (clickable annotations mapping to source documents)
- **Confidence indicators** — show whether a fact is well-supported (multiple recent sources) or uncertain (single source, stale)
- **Contradictions shown explicitly** — flagged for physician review, not silently resolved
- Combining high explainability with high confidence **reduced clinician override rates from 87.6% to 33.3%** in one study
- Position as "reconciled clinical picture with evidence" — NOT "current truth" (the word "truth" implies the system knows more than the doctor)

---

## How Successful AI Startups Integrated Into Epic

Every winner follows the same pattern:

| Company | UI Pattern | Integration | Adoption Result |
|---------|-----------|-------------|----------------|
| **Regard** | Sidebar panel, proactive draft note | Embedded in Epic | 150+ hospitals, 30% time savings |
| **Navina** | One-page Patient Portrait | Chrome extension → Epic BPA → Showroom | 86% weekly adoption, 61% prep time reduction, 90% adoption week one at Jefferson City |
| **Abridge** | Recording button in Haiku → draft note in Epic tab | SMART on FHIR + Epic Workshop partnership | 250+ health systems, 86% less writing effort |
| **TransformativeMed** | Replaces default patient list with specialty dashboards | Native embedding (Cerner MPages, expanding to Epic) | 2026 Best in KLAS, 45 min/day saved |

**Universal rules:**
- Embed inside Epic, never replace it
- Pre-load value before the encounter
- Consolidated information in one place beats scattered alerts
- Zero extra navigation steps
- Show provenance obsessively

---

## Regulatory and Compliance Context

- **FDA**: January 2026 revised CDS guidance creates clear Non-Device CDS exemption for tools that present reconciled clinical information for physician review (not autonomous recommendations). Our product likely qualifies.
- **HIPAA**: Standard requirements. Need BAA with cloud provider (AWS/GCP). HITRUST e1 certification achievable for ~$30K in 10 weeks.
- **Cures Act / Information Blocking**: Hospitals legally required to provide third-party FHIR read access. $1M/violation penalties. HHS-OIG issued first enforcement letters in February 2026.
- **No HITRUST required on day one** — can start with SOC 2 + BAA, add HITRUST for enterprise sales later.

---

## Data Access: What Epic's FHIR APIs Actually Provide

- **750+ no-cost FHIR R4 APIs** at open.epic.com
- Structured data: Patient, Condition (problem list), MedicationRequest, AllergyIntolerance, Observation (labs/vitals), Encounter, Procedure, DiagnosticReport — all accessible
- **Clinical notes**: Cures Act mandates access to 8 note types (discharge summaries, H&P, progress notes, consultations, etc.) via DocumentReference
- **Critical limitation**: Epic does not reliably populate `meta.lastUpdated` — cannot rely on FHIR-native change detection. Must build own temporal tracking by capturing periodic snapshots.
- **Rate limits and session scope**: Pure real-time FHIR querying during a 15-minute encounter is infeasible for comprehensive data. Need a **persistent backend** that ingests data periodically via backend OAuth 2.0 or Bulk FHIR.
- **Each hospital's FHIR configuration is different** — endpoint availability, resource types enabled, and write permissions vary by site.

---

## Product Name: Andy

**useandy.com** — "The AI that already reviewed the chart for you."

Human names are the proven pattern in healthcare AI (Epic's "Art", Regard's "Max", Suki). The name conveys a helpful colleague, not a system claiming authority. Hospital buyers (CMIOs/CIOs) are tech-savvy and don't need clinical naming.

---

## Customer and User

**Buyer:** CMIO or VP of Population Health at a value-based care organization (IPA, ACO, large primary care group). They care about revenue capture, quality scores, and physician retention.

**User:** Primary care physician (internal medicine / family medicine) doing pre-visit chart review in VBC practices. Sees 20+ patients/day, spends 5+ minutes per patient navigating charts.

**Target patient profile:** Complex chronic Medicare patient — e.g., 67-year-old woman with Type 2 diabetes, hypertension, CKD stage 3, depression. Sees PCP quarterly, endocrinologist twice/year, nephrologist annually. 200+ notes across 15 years from 6+ providers. Problem list missing CKD. Medication list still shows metformin discontinued 4 months ago by nephrologist.

---

## Why Pre-Visit is the Right Wedge

Chart review (the *input* side — reading records to understand the patient) consumes 33% of all EHR time — the single largest activity, exceeding documentation (24%). The entire ambient scribe market ($600M, 30+ competitors) attacks documentation. Almost nobody attacks chart review.

Pre-visit is the only workflow moment with **direct VBC revenue linkage** — HCC recapture and RAF score improvement happen here. One health system generated $18.5M in additional revenue from pre-visit HCC recapture (6x ROI). Care transitions are a bigger safety problem but require a different buyer and sales motion — that's the expansion path at 18-24 months.

The "what changed since last visit" differential view appears to be an **unoccupied product position** — no tool in the market, including Navina, explicitly offers this.

---

## What a PCP Reviews Pre-Visit (12 Data Types)

Always reviewed: problem list, medication list, allergies, recent labs, recent vitals, last visit note, chief complaint.

Usually reviewed: specialist consultation notes, imaging reports, care gaps/health maintenance, immunization status, hospitalization/ED records.

Each maps to FHIR R4 with US Core profiles. The three data types most urgently needing temporal supersession detection: **problem lists** (40% of diagnoses missing), **medication lists** (60% have discrepancies), **clinical notes** (82% is copy-pasted/auto-imported).

---

## Development Data Strategy (Finalized)

### Epic's sandbox is useless for clinical AI
~8 test patients, minimal data, no real notes, no messiness. Designed for OAuth testing, not product development.

### Approach: LLM-based via API, not custom NLP training
We use Claude/GPT-4 via API for note parsing, temporal reasoning, and contradiction detection. No custom model training needed. Specialized NLP datasets (i2b2, MedNLI) are used only as evaluation benchmarks to measure accuracy.

### Development datasets (in priority order)

| # | Dataset | What it is | Role for Andy |
|---|---------|-----------|---------------|
| 1 | **Synthea** | Free software that generates fake patients with realistic medical histories in FHIR R4. Longitudinal timelines of visits, diagnoses, medications, labs spanning years. | Core foundation. Generate 1,000+ primary care patients. Outputs 10 of 12 pre-visit data types natively. |
| 2 | **Chatty-Notes + custom LLM pipeline** | Takes Synthea's structured data and uses LLMs to write realistic doctor notes for each visit. | Fill Synthea's biggest gap: it has no narrative clinical text. Generate progress notes, specialist letters, discharge summaries. |
| 3 | **Error injection layer (we build)** | Script that deliberately breaks clean Synthea data to match real-world messiness. Every error is labeled with type, severity, and ground truth. | Make data realistic. Inject: ~40% missing problem list entries, ~60% medication discrepancies, ~50% copy-paste duplication, ~30% missing specialist notes. Creates labeled evaluation corpus. |
| 4 | **MIMIC-IV-Note** | 331,000 real discharge summaries and 2.3M radiology reports from a Boston hospital. Real messy doctor-written text. | Style reference only. Use as examples of how real notes look (abbreviations, templates, copy-paste artifacts) to calibrate LLM note generation. NOT primary development data — it's ICU-only, no primary care. |

### Evaluation benchmarks (not development data)

| Dataset | What it tests |
|---------|--------------|
| **i2b2 2012 Temporal Relations** | Does our system correctly understand when things happened? (BEFORE, AFTER, OVERLAP) |
| **MedNLI** | Does our contradiction detection work? (agrees / contradicts / unrelated) |
| **EMNLP 2023 Clinical Contradiction** | Larger-scale contradiction detection accuracy |

### Later-stage validation

| Program | When | What it provides |
|---------|------|-----------------|
| **Mayo Clinic Platform_Accelerate** | When prototype works | 13.6M real patient records including primary care. Apply 3x/year. |

### Why MIMIC-IV was downgraded from core to reference
MIMIC-IV is exclusively ICU data from one hospital. It has no outpatient progress notes, no specialist referral letters, no primary care problem lists, no care gaps. Our product is for primary care pre-visit prep — MIMIC-IV doesn't match the clinical context. Use it only as a style guide for realistic note generation.

---

## Development Quick Reference

### Local MVP is fully buildable
- Synthea + LLM notes + error injection gives you everything needed
- Epic sandbox useful only for testing OAuth flow and FHIR API parsing
- Epic's launchpad simulates in-Epic SMART on FHIR launch flow
- Build and demo entire product on synthetic patients with contradictions, stale meds, outdated problems

### When you need a hospital
- First time you need a real hospital is for pilot (real patient data)
- Hospital's IT team grants FHIR access — not Epic corporate
- Epic Showroom listing is optional, helps scale later

### Suggested stack (non-binding, for context)
- Frontend: React (SMART on FHIR JS libraries exist)
- Backend: Python/FastAPI (best AI/NLP ecosystem)
- Database: PostgreSQL with temporal schema
- AI: LLM via API (Claude/GPT-4) for clinical note parsing + temporal reasoning
- Auth: OAuth 2.0 (required by SMART on FHIR spec)
- Infra: AWS or GCP with HIPAA BAA

---

## Strategy Decisions Log

| Decision | Rationale |
|----------|-----------|
| **Start narrow** (temporal truth layer only) | 18 case studies: zero seed-stage companies succeeded broad. Expand to clinical intelligence platform at 18-24 months. |
| **Pre-visit wedge** | 33% of EHR time is chart review. Only workflow moment with direct VBC revenue linkage. Far less competitive than during-encounter (ambient scribe) market. |
| **Primary care first** | Highest chart review volume, longest patient relationships, VBC revenue alignment. Expand to ICU and ED later. |
| **API not training** | Claude/GPT-4 handles clinical text well enough for MVP. Use NLP datasets for evaluation only. |
| **Synthea over MIMIC-IV** | MIMIC-IV is ICU-only, no primary care. Synthea generates longitudinal primary care FHIR data matching our clinical context. |
| **SF location** | UCSF and Stanford are innovation-friendly Epic hospitals 20 min away. Both already running AI inside SMART on FHIR. |

---

## Key Risks (Honest Assessment)

### Near-fatal risk: Timing
- Build + validate: 12–18 months. Sell to first hospitals: 12–24 months. Total: 24–42 months.
- Epic can ship competing features: 6–12 months from announcement.

### Significant risks
- Navina is one feature sprint away from adding temporal features
- "Data quality" isn't a purchasing category — must sell as revenue/risk adjustment/safety
- Clinical NLP accuracy — hallucination rates of 1.5–3.5% require robust fact-checking
- Per-site deployment — each hospital requires individual configuration

### Mitigating factors
- Nobody has built this exact product (confirmed across exhaustive search)
- The technical difficulty IS the moat — temporal supersession is genuinely hard
- Cures Act legally protects data access ($1M/violation penalties)
- Regard proves third-party-on-Epic model works at 150+ hospitals
- FDA path is clear (Non-Device CDS exemption)
