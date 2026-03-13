# Chakravyuh Backend — Task Checklist

## Phase 0: Documentation
- [/] Create `project_description.md` with full project details

## Phase 1: Scaffold & Core Files
- [/] Create `requirements.txt`
- [/] Create `Dockerfile`
- [/] Create `docker-compose.yml`
- [/] Create `app/__init__.py`
- [/] Create `app/models.py` (Pydantic schemas)

## Phase 2: Game Logic
- [x] Create `app/math_engine.py` (EMI calc, penalties, monthly tick)

## Phase 3: AI Agents (LangGraph)
- [x] Create `app/agents/__init__.py`
- [x] Create `app/agents/llm_provider.py` (Groq multi-key rotator)
- [x] Create `app/agents/graph.py` (LangGraph state machine)
- [x] Create `app/agents/marketer.py` (scenario generation)
- [x] Create `app/agents/auditor.py` (post-mortem reports)

## Phase 4: API Layer
- [x] Create `app/main.py` (FastAPI routes: `/api/start`, `/api/action`)

## Phase 5: Verification
- [x] Validate Pydantic models
- [x] Docker build succeeds
- [x] API smoke test (structural — 21/21 passed; Docker — health check OK)
