# Recruitment Operations Intelligence & Decision Support System

**Live demo:** https://recruitment-operations-intelligence.onrender.com

An end-to-end recruitment analytics system that turns scattered recruiter Excel trackers into a single decision-support dashboard — candidate identity reconciliation, funnel analytics, reusable-talent detection, JD-to-candidate matching, joining-risk scoring, and recruiter prioritization, all served through one deployed Gradio interface.

---

## 1. Problem Statement

Recruitment operations at a consultancy run on Excel. Every recruiter maintains their own tracker, with their own column names, their own status labels, and their own way of recording the same event. Over a hiring cycle this produces four concrete, measurable problems:

1. **No single source of truth.** The same candidate can appear in multiple recruiter sheets with slightly different names, phone numbers, or role tags, with no shared key to merge on. Leadership cannot answer "how many unique candidates have we actually engaged?" without a manual audit.
2. **Invisible funnel leakage.** A role sourced with 40+ profiles might convert only 2–3 to offer. Without a structured funnel view, no one can see *at which stage* candidates are dropping — sourcing, screening, shortlisting, or interview — so the fix (better sourcing vs. better screening vs. better client alignment) is guesswork.
3. **Wasted candidate value.** A candidate rejected for one role is frequently a strong fit for a different, currently-open role. With no cross-role visibility, recruiters re-source from zero instead of re-activating a known, already-vetted candidate.
4. **No systematic joining-risk tracking.** An accepted offer is not a guaranteed join — notice period, counter-offers, and competing offers all affect it — but there was no structured way to flag which accepted candidates were actually at risk of falling through before day one.

Before writing any code, I documented this problem formally in a project requirements PDF (`Recruitment_Intelligence_Project_Anchor.pdf`) — a spec covering the target modules, the data this would run on, and explicit constraints (no fabricated financial/ROI claims, PII and client confidentiality must be preserved end-to-end). That document was the working reference for the entire build: every module below traces back to one of the four problems above, and anything that didn't map to a real operational gap was cut, regardless of how good a portfolio feature it might have made.

## 2. Solution Overview

The system is built as a linear pipeline (developed and validated in a 32-step Jupyter notebook) that ends in a single deployed dashboard:

| # | Module | Solves |
|---|---|---|
| 1 | Candidate reconciliation | Problem 1 — merges multi-source trackers into one candidate record using evidence-based identity resolution (name + role + interview-date agreement), not exact-string matching |
| 2 | Funnel & client-performance analytics | Problem 2 — stage-wise conversion rates by role and by client |
| 3 | Candidate 360° / reusable-pool detection | Problem 3 — surfaces every candidate who maps to more than one role |
| 4 | JD ↔ candidate matching | Problem 3 — paste a new JD, get ranked candidates from the existing pool, no re-sourcing |
| 5 | Joining-risk scoring | Problem 4 — flags HIGH/MEDIUM/LOW risk from notice period and status signals |
| 6 | Recruiter prioritization (P1–P4) | Turns the above into a ranked, actionable worklist |
| 7 | Confidentiality masking | Real client names never reach the public dashboard — mapped to anonymized business-group categories everywhere |
| 8 | Gradio dashboard | Delivers all of the above through tabs a recruiter can use with zero technical background |

**Current scope vs. the original spec:** the anchor document lays out a 7-module system including live multi-file ingestion and sourcing-portal cost/ROI tracking. This build ships modules 1–8 above as a working, deployed slice. Multi-recruiter live ingestion, portal-cost ROI, and automated outreach generation are documented as next steps in Section 10 rather than built — they need data sources (live tracker feeds, per-portal spend) this dataset doesn't include.

## 3. Architecture

```
 Recruiter/Client Excel + CSV data
              │
              ▼
   CANDIDATE RECONCILIATION
   (name/email keys + evidence-based
    identity resolution: role + interview
    date agreement, not just name match)
              │
              ▼
   CENTRAL CANDIDATE DATASET (frozen)
              │
   ┌──────────┼───────────────┐
   ▼          ▼               ▼
FUNNEL &   CANDIDATE 360° /  CONFIDENTIALITY
CLIENT     REUSABLE POOL     MASKING
PERFORMANCE (multi-role      (real client names →
ANALYSIS    candidates)       anonymized business groups)
   │          │               │
   └──────────┼───────────────┘
              ▼
      JD ↔ CANDIDATE MATCHING
      (paste a JD → rule-based
       similarity score + level)
              │
              ▼
      JOINING-RISK SCORING
      (notice period / status /
       offer signals → HIGH/MED/LOW)
              │
              ▼
   RECRUITER PRIORITIZATION
   (P1 Immediate Review → P4 Low Priority)
              │
              ▼
   GRADIO DASHBOARD (app.py)
   Overview | Matching & Quality |
   Risk & Priority | Recommendations
              │
              ▼
   Deployed: GitHub → Render (free tier)
```

## 4. Why a Rule-Based Engine, Not an LLM

- **Explainability.** A recruiter or client asking "why is this candidate HIGH risk?" needs a traceable answer (notice period + status), not a black-box embedding score. Every score in this system is explainable in one sentence.
- **Dataset scale.** With ~800 unique candidates and 20 roles, structured field matching + text similarity (`difflib.SequenceMatcher`) delivers comparable practical accuracy to embeddings, without extra latency, cost, or dependencies.
- **No hallucination risk in HR decisions.** A model inventing a plausible-sounding justification for a risk flag is worse than no justification, when the flag affects a real hiring decision.
- **Zero-cost, zero-dependency operation.** No API keys, no rate limits — it runs the same way on a recruiter's laptop as it does on a $0 free-tier host.
- This is a deliberate architecture choice, not an oversight: an earlier prototype of this same problem (`recruitment-intelligence-dashboard`) used the Groq API (Llama) to generate plain-English risk explanations and outreach copy. For this build, the scoring/matching core was kept fully rule-based and auditable, with an LLM layer left as a clearly scoped future addition purely for natural-language explanation text — not for the decision logic itself.

## 5. Tech Stack

| Layer | Tool | Why |
|---|---|---|
| Language | Python | Notebook prototyping → single-file deployable app |
| Data processing | Pandas, NumPy | Cleaning, reconciliation, aggregation |
| Matching engine | `difflib.SequenceMatcher` | Identity resolution + JD-candidate matching — explainable, dependency-free |
| Visualization | Matplotlib | Server-rendered donut/bar charts embedded in the dashboard |
| UI | Gradio (`gr.Blocks`) | Multi-tab, file-upload, zero-frontend-code interface |
| Dev environment | Google Colab | 32-step iterative build, version history preserved in the `.ipynb` |
| Version control | Git / GitHub | `Priya2523/recruitment-operations-intelligence-dashboard` |
| Deployment | Render (free tier) | Selected after evaluating Hugging Face Spaces (Gradio/Docker SDKs now paid-tier), AWS EC2 (works, but no free ongoing tier), and Colab-hosted tunnels (proxy breaks Gradio's SSE/queue layer) |
| Explored, not shipped | Groq API (Llama), SQLite, Flask + ngrok, Streamlit, AWS EC2 | Evaluated during earlier iterations/deployment attempts; excluded from the final build to keep the shipped system dependency-light |

## 6. Engineering Challenges & Solutions

- **Cross-source identity resolution.** The candidate master and the recruiter shortlist tracker had no shared clean key — inconsistent name spellings, missing emails. Built a multi-signal resolver combining normalized name, role-text similarity, and interview-date agreement, with a confidence threshold gating a REVIEW tier instead of forcing every row into a match.
- **Threshold calibration.** Initial role-similarity gate (0.65) rejected known-correct matches whose source role text was generic. Re-tuned to 0.35 after testing precision against a labeled set of confirmed matches.
- **Malformed source files.** Multi-sheet Excel exports contained repeated header rows and blank separators mid-file, which had to be detected and stripped before any row count could be trusted.
- **Confidentiality by design.** Built a `CLIENT_MAP` masking layer so the public dashboard shows only anonymized business-group categories, never real client names — expanded from an initial 7-key map to the full 11-client set, and applied consistently across every downstream chart and table, including ones added after the initial build.
- **Deployment portability.** Colab's port-forwarding proxy breaks Gradio's SSE/queue connection regardless of Gradio version — a known platform-level incompatibility, not a config issue. Validated the dashboard logic on AWS EC2 (works, but not cost-free long-term), then standardized on GitHub-connected Render deployment for a permanent, free, zero-maintenance host.
- **Graceful degradation for unseen data.** The JD-matching module checks for a pre-computed `match_level` column first, computes similarity live against a pasted JD if absent, and states plainly when neither is available — so the dashboard never silently shows an empty or misleading chart.


## 7. Results

On the working candidate pool (~15K candidate-role records, ~800 unique candidates, across 20 roles):

- The large majority of the unique candidate pool qualifies as **reusable across more than one role** — a ready-made pipeline that reduces net-new sourcing load.
- A small fraction of candidate-role pairs are **HIGH-quality matches**, while a large share currently show **NO MATCH** — pointing to a sourcing/tagging gap rather than a candidate-quality gap.
- Roughly a quarter of candidates fall into **HIGH joining-risk** — the segment recruiters should prioritize for pre-offer follow-up.
- **Technology & Business Consulting** is the largest single demand center by recruitment volume.




   

## 9. Run Locally

```bash
git clone https://github.com/Priya2523/recruitment-operations-intelligence-dashboard.git
cd recruitment-operations-intelligence-dashboard
pip install pandas numpy gradio matplotlib openpyxl
python app.py
```

Open `http://localhost:7860`, upload a CSV/XLSX tracker, and optionally paste a JD to run live match scoring against the existing candidate pool.

## 10. Deployment & Roadmap

- **Code:** GitHub — `Priya2523/recruitment-operations-intelligence-dashboard`
- **Hosting:** Render (free tier), auto-deploys on push
- **Live:** https://recruitment-operations-intelligence.onrender.com

**Roadmap (scoped, not yet built):**
- Live multi-recruiter ingestion pipeline (replacing the current single pre-cleaned file + JD-paste flow)
- Sourcing-portal cost/ROI tracking, once per-portal spend and usage data is available
- LLM layer (Groq/Llama, already prototyped separately) on top of the existing rule-based scores, to auto-generate recruiter-facing explanation and outreach copy while keeping the scoring engine itself fully rule-based and auditable
- Automated recruiter messaging/outreach generation

---

*Built as a Summer Internship Project (SIP). Candidate PII and real client names are never exposed in the public dashboard or this repository.*
