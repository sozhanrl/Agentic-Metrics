# Agentic AI-Based Software Metrics Prioritization and Recommendation System

## What changed in this refined version

**Backend**
- All 5 database tables now have matching SQLAlchemy models (previously only `projects` was modeled)
- Full CRUD layer for projects, metric values, recommendations, and feedback
- A real prioritization engine (`app/recommendation_engine.py`) that scores metrics against targets and produces ranked, explained recommendations with a step-by-step reasoning trail
- An optional LLM narration layer (`app/ai_engine.py`) that rewrites explanations more naturally if you set `ANTHROPIC_API_KEY` — falls back gracefully if not set
- Proper routers for `/projects`, `/metrics`, `/recommendations`, `/feedback`
- A `/dev/seed/{project_id}` endpoint to populate realistic demo data before your real Azure DevOps/GitHub/SonarQube connectors exist
- Removed the old duplicate root-level `main.py`/`database.py` — everything now lives under `app/`

**Frontend**
- A full React (Vite) dashboard: sidebar with project switching, KPI strip, a priority queue of recommendation cards with an expandable "agent reasoning trail," and a metrics panel grouped by category
- Custom design system (see `frontend/src/index.css`) — not a default template

## Setup

### Backend
```powershell
cd backend
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```
Copy `.env.example` to `.env` and paste in your real Neon `DATABASE_URL` (and optionally `ANTHROPIC_API_KEY`).

Run the schema in `db/schema.sql` against your Neon database if you haven't already (it's idempotent-safe to re-run only if your tables don't already exist — check first).

Start the API:
```powershell
uvicorn app.main:app --reload
```
Visit http://127.0.0.1:8000/docs to confirm it's running.

### Frontend
```powershell
cd frontend
npm install
```
Copy `.env.example` to `.env` (default API URL is already correct for local dev).

```powershell
npm run dev
```
Visit the URL it prints (usually http://localhost:5173).

## Patentable Core Invention: Evidence-Adaptive Arbitration Mechanism

This project implements **Evidence-Adaptive Arbitration between Direct Feedback and Causal-Graph-Propagated Learning**, a closed-loop multi-agent mechanism for software metrics prioritization:

- **Per-Metric Meta-Learning Strategy Selector** (`app/agents/strategy_selector.py`): Dynamically arbitrates between `pure_bayesian`, `graph_propagated`, and variance-weighted `hybrid` learning strategies based on sample count, posterior variance, metric predictiveness, and incoming causal edge confidence.
- **Self-Evolving Causal Knowledge Graph** (`app/agents/evolving_graph.py`): Automatically strengthens confirmed causal edges and retires refuted edges when their strength drops below the removal threshold.
- **Context Memory Engine** (`app/agents/context_memory_engine.py`): Learns metric predictiveness and Bayesian priors per project archetype.
- **Full Specification & Section 3(k) Framing**: See [`PATENT_MECHANISM.md`](file:///p:/Metric%20project/metrics-agent/PATENT_MECHANISM.md).

### Verification & Reproduction

Run unit test suites:
```powershell
cd backend
.\venv\Scripts\python.exe -m pytest tests/ -v
```

Run multi-cycle synthetic scenario demonstration artifact:
```powershell
cd backend
.\venv\Scripts\python.exe demo_patent_mechanism.py
```

## First run walkthrough
1. Start the backend, then the frontend
2. In the UI, click **"+ New project"**, fill in a name/source, create it
3. Click **"Seed demo data"** — this populates realistic metric values
4. Click **"Run agent"** — this triggers the prioritization engine and populates the priority queue
5. Click any recommendation card to expand its **reasoning trail** and see exactly which metric inputs drove that priority score

