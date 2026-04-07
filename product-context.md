# Andy — Product Context

## One-liner
AI teammate that knows everything about your projects.

## What is this
A per-project scoped knowledge base that bridges enterprise docs (Confluence, Notion, Slack, Google Docs) into a working KB that serves both humans and AI coding agents (Cursor, Claude Code, Copilot). It's what CLAUDE.md files want to be — collaborative, self-maintaining, and scalable.

## The core insight
Enterprise-scale KB has been impossible because everyone tries to build one giant coherent KB. The fix: create separate smaller KBs per project/team that are small enough to stay accurate. Trade org-wide coherence for per-scope coherence.

This is architecturally opposed to what every incumbent is building. Glean, Notion, Confluence, Guru — all position around "one big graph" or "single source of truth." This thesis says that's fundamentally wrong. Fragmentation isn't the disease — it's the correct architectural response to the coherence problem at scale.

## Why KB at enterprise scale fails
- 30-40% of wiki content goes stale within 6 months — a human behavior constant, not a software variable
- Wikis don't scale beyond ~50 people (Friday.app observation, confirmed by multiple sources)
- Academic research confirms scope and coherence trade off against each other with decreasing returns to scale (Nesta & Saviotti 2005, Sarkar & Ramaswamy 2000)
- Every KM product positions around "single source of truth" — yet 50-70% of KM initiatives fail

## Why per-scope KB works
Smaller scope means:
- Retrieval can't fail because the search space is small enough for full context
- Entity resolution becomes trivial (the team knows "the new dashboard" = "Product X")
- Temporal supersession is captured naturally (the team knows Jenkins was replaced by GHA)
- Contradictions are resolvable because they're within a single project's context
- Git-backed markdown enables instant rollback to any known-good state (unlike knowledge graphs where noisy data corrupts nodes/edges irreversibly)

## The "two worlds" gap
Two parallel knowledge universes exist that don't talk to each other:

**World 1: Enterprise docs** (Confluence, Notion, Slack, Google Docs)
- Where humans actually write knowledge
- Served to humans via Glean/Guru/Confluence search
- Agents access via MCP but it's just RAG over the raw mess — no synthesis, no curation

**World 2: Agent context** (CLAUDE.md, .cursorrules, AGENTS.md, Mem0, Letta)
- Created separately, specifically for agents
- Either manually written from scratch or auto-extracted from code only
- Humans don't read or benefit from this

Nobody bridges the two. No product takes scattered enterprise docs humans already wrote, synthesizes them into a coherent per-project KB, and serves that KB to both humans (as a browsable wiki) and AI agents (via MCP/CLAUDE.md).

## Where retrieval fundamentally fails (why write-time curation matters)
RAG/search fails systematically on these cases. Write-time curation into a scoped KB solves them:

1. **Terminology mismatch:** "Product X" vs "the new dashboard" vs "Project Phoenix" vs "PLAT-2847." Embedding similarity between semantically dissimilar aliases falls below thresholds. Entity resolution is stuck at 62-75% F1 after 50 years of research.

2. **Implicit temporal supersession:** "Pushed the GHA config, pipeline's green" doesn't trigger invalidation of Jenkins references. No explicit "we migrated from Jenkins" statement exists. Temporal KG research assumes explicit timestamps only.

3. **Distributed/emergent knowledge:** A decision made across 6 meetings where no single document says "we decided X." Cross-document extraction benchmarks show ~68% F1 (CodRED). Knowledge exists only as the intersection of multiple sources.

4. **Scope-qualified contradictions:** "We use microservices" is true generally but false for billing (consolidated to monolith). Triple-based KGs struggle to represent two facts true in different contexts. Reasoning over scoped facts is PSpace-complete.

## The key reframe: retrieval is the bottleneck, not inference
If retrieval surfaces all relevant documents, the LLM reconciles perfectly at inference time. The problem is retrieval misses things — terminology drift, implicit supersession, distributed decisions. Write-time curation into a scoped KB ensures retrieval never misses because the answer already exists as a resolved, curated artifact.

This is NOT "reconciliation as a feature." This is "per-scope separation as architecture." The reconciliation happens naturally when the scope is small enough for the LLM to hold full context at write time.

## Who it serves
Both humans AND AI coding agents:
- **Humans:** Browse it as a wiki. Onboard new team members. Find authoritative answers about the project.
- **AI agents:** Consume it via MCP. Cursor, Claude Code, Copilot get accurate project context on every task. Reduced hallucinations, better architectural adherence, fewer rework cycles.

AI agents are the killer differentiator: a non-human consumer that uses the KB every minute without documentation fatigue. This breaks the historical KM failure pattern where wikis die because humans stop reading/writing.

## What this is NOT
- NOT a search engine over raw docs (that's Glean)
- NOT a manually-maintained wiki (that's Confluence)
- NOT auto-generated code docs (that's Mintlify, Swimm)
- NOT agent memory from conversations (that's Mem0, Letta)
- NOT a codebase graph (that's Greptile, Augment Code)
- NOT an enterprise-wide operational playbook (that's Edra)

## Positioning — critical
Position as **AI coding infrastructure**, NOT knowledge management.

| Position as... | What happens |
|---|---|
| "Knowledge management" / "AI wiki" | KM graveyard. Competes with free Confluence. 50-70% failure rate. Slab took 9 years to reach $3M. |
| "AI coding context infrastructure" | New budget category. Competes with Cursor ($40/seat), Copilot Enterprise ($39/seat). $2B+ ARR companies exist. |

The words matter. "Knowledge base" triggers the wiki graveyard. "Context layer for AI agents" triggers the AI productivity budget.

## Three conditions for success
1. **Position as AI coding infrastructure, not KM.** The KM category carries a death sentence. The AI coding tools category carries $2B+ ARR companies.

2. **Auto-generate 80%+ of content.** Every KM failure traces to "engineers won't write docs." The product must auto-extract from code, PRs, Slack conversations, meeting notes — and only ask humans to annotate at natural workflow moments (PR reviews, architecture decisions, incident responses).

3. **Show measurable AI agent improvement.** If the product proves Cursor/Claude Code produce better code when connected to the KB — reduced hallucinations, fewer rework cycles, better architecture adherence — it creates quantifiable ROI that traditional KM tools never had.

## Context layer, not automation
Focus on being the knowledge layer that makes every agent better, not an agent itself. Engineering tasks are too varied to automate coherently — unlike ITSM (Edra's domain) where "handle a password reset" has the same 5 steps every time. Let Cursor automate the coding. Let Claude Code automate the debugging. Andy makes both of them smarter by giving them accurate project context.

Be the brain, not the hands.

## Competitive landscape summary
- **40+ adjacent companies** across 5 categories (codebase context engines, AI-maintained docs, team wikis, agent memory, enterprise knowledge automation)
- **$1.9B in funding** in the broader AI coding context category
- **Nobody combines all 5 properties:** per-project scoped + self-maintaining + human knowledge + code knowledge + serves both humans and AI agents
- **Closest threats:** Swimm 2.0 (4/5 properties, locked into legacy modernization), Potpie AI ($2.2M, code-only), Kodingo (appears vaporware)
- **Edra** ($30M Sequoia) validates the core architecture (ingest scattered data → reconcile → serve humans + agents) but targets ITSM/operations, not engineering
- **Platform risk:** Cursor has Memories + Team Rules + Notepads. Claude Code has hierarchical CLAUDE.md + Auto Memory. Copilot has Spaces. 12-18 month window before simplest use cases absorbed.

## What Glean/Guru actually are (and aren't)
- **Glean** ($7.2B valuation): Index over raw docs + RAG at query time. It's a search engine, not a KB. No reconciliation, no synthesis, no curation.
- **Guru** ($63M ARR): Human-written cards with verification workflow + MCP server serving curated cards to agents. Closest from the KB side, but requires manual human curation — no autonomous synthesis from scattered sources.
- **Confluence/Notion MCP:** Thin CRUD wrappers returning raw pages as markdown. No curation layer.

## Demand signals
- CLAUDE.md files prove developers are building scoped KBs manually today
- awesome-cursorrules repo: 37,800 GitHub stars for a collection of config files
- AGENTS.md adopted in 60,000+ repos, governed by Linux Foundation
- Research: AGENTS.md files reduced agent runtime by 29% and output tokens by 17%
- ETH Zurich finding: human-written context improves agent performance; auto-generated context hurts it (-3% success rate)
- Karpathy's "LLM Wiki" post (April 4, 2026): 11M+ views, called it "an incredible new product"

## Pricing and unit economics
- $20-50/seat/month validated by comparable tools: Cursor Teams ($40), Copilot Enterprise ($39), Sourcegraph ($59), Guru ($25)
- 72-89% gross margins at these price points
- ROI math: at $150K loaded salary ($72/hr), saving 15-30 min/day = $396-792/month value vs $20-50 tool cost
- For 100-engineer team at $40/seat: $48K ACV

## Key risks
1. **Platform absorption** (12-18 month window) — Cursor/Claude Code/Copilot building native context management
2. **KM graveyard** (50-70% failure rate) — if positioned as wiki/KM instead of AI coding infrastructure
3. **Can't auto-generate enough content** — if it requires human writing effort, it fails like every wiki
4. **Unclear buyer** — engineering lead? VP Eng? DevEx team? Nobody clearly owns this budget
5. **Feature vs product** — could be an MCP server plugin, not a standalone company

## The thesis novelty (~70% known, ~30% genuinely novel)
Individual observations are well-documented: wikis fail at scale, teams fragment naturally, smaller scope = higher quality, data mesh (Dehghani 2019) made the same argument for data platforms. What's new is the specific synthesis: coherence as the binding constraint, deliberate scope reduction as the solution, and the explicit rejection of org-wide coherence as a goal. No product, paper, blog post, or founder has assembled these pieces. Every incumbent is architecturally committed to the opposite philosophy — they can't copy this without contradicting their core product.

## Distribution playbook
- MCP integration on day one (universal socket for AI agents)
- IDE-native presence (where developers already work)
- Git-native storage (docs in repo, lowest adoption friction)
- Mintlify proved this playbook: $0 → $10M ARR via docs-as-code + YC network
