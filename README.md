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

## First run walkthrough
1. Start the backend, then the frontend
2. In the UI, click **"+ New project"**, fill in a name/source, create it
3. Click **"Seed demo data"** — this populates realistic metric values
4. Click **"Run agent"** — this triggers the prioritization engine and populates the priority queue
5. Click any recommendation card to expand its **reasoning trail** and see exactly which metric inputs drove that priority score
