# Chakravyuh Backend — Implementation Plan

A stateless, turn-based, adversarial financial survival simulator. The user survives 12 virtual months against AI-generated financial emergencies. The backend is fully stateless — the Next.js frontend passes the full JSON game state on every request.

## Proposed Changes

### Documentation

#### [NEW] [project_description.md](file:///C:/Users/yugan/.gemini/antigravity/scratch/chakravyuh/backend/project_description.md)
Comprehensive project overview covering game concept, tech stack, schema, game mechanics, API contracts, and directory structure. Serves as the single-source-of-truth reference for all contributors.

---

### Scaffolding & Infrastructure

#### [NEW] [requirements.txt](file:///C:/Users/yugan/.gemini/antigravity/scratch/chakravyuh/backend/requirements.txt)
Python dependencies:
- `fastapi`, `uvicorn[standard]` — API server
- `pydantic` — data validation
- `langchain`, `langchain-groq`, `langgraph` — AI orchestration (Groq free tier)
- `python-dotenv` — env var loading

#### [NEW] [Dockerfile](file:///C:/Users/yugan/.gemini/antigravity/scratch/chakravyuh/backend/Dockerfile)
- Base: `python:3.11-slim`
- Install deps, copy app code, expose 8000, run via Uvicorn

#### [NEW] [docker-compose.yml](file:///C:/Users/yugan/.gemini/antigravity/scratch/chakravyuh/backend/docker-compose.yml)
- Single `backend` service on port 8000
- Volume mount for hot-reload during dev
- Env file passthrough for `GROQ_API_KEYS`

---

### Pydantic Models

#### [NEW] [models.py](file:///C:/Users/yugan/.gemini/antigravity/scratch/chakravyuh/backend/app/models.py)
Strict Pydantic models matching the GameState schema from the spec:
- `Metrics`, `Persona`, `Loan`, `Transaction`, `ScenarioOption`, `Scenario`, `GameState`
- `ActionRequest` (request payload for `/api/action`)
- Enum `OptionType` with values `safe_drain`, `emi_trap`, `stress_spike`
- Validators: stress clamped 0–100, month 1–12, options list must have exactly 3 items

---

### Game Logic

#### [NEW] [math_engine.py](file:///C:/Users/yugan/.gemini/antigravity/scratch/chakravyuh/backend/app/math_engine.py)
Pure functions for deterministic financial logic:
- `apply_choice()` — resolve `safe_drain` / `emi_trap` / `stress_spike`
- `calculate_emi()` — EMI from principal, APR, term (predatory 24% over 6 months)
- `monthly_tick()` — add income, deduct rent, service all EMIs, bounce-fee penalty
- `check_game_over()` — cash < 0 or stress ≥ 100 → loss; month == 12 → win

---

### AI Agents (LangGraph)

#### [NEW] [agents/\_\_init\_\_.py](file:///C:/Users/yugan/.gemini/antigravity/scratch/chakravyuh/backend/app/agents/__init__.py)
Empty init.

#### [NEW] [agents/marketer.py](file:///C:/Users/yugan/.gemini/antigravity/scratch/chakravyuh/backend/app/agents/marketer.py)
- System prompt instructs the LLM to act as a predatory marketer
- Receives persona + current metrics + active loans
- Returns a `Scenario` with exactly 3 options (one per `OptionType`)
- Uses LangChain `PydanticOutputParser` for structured output
- Uses `ChatGroq` (model: `llama-3.3-70b-versatile`) via round-robin key rotation

#### [NEW] [agents/auditor.py](file:///C:/Users/yugan/.gemini/antigravity/scratch/chakravyuh/backend/app/agents/auditor.py)
- System prompt: forensic financial auditor
- Receives full game state history
- Also uses `ChatGroq` via the shared key rotator
- Returns a `post_mortem_report` string (loss analysis or victory debrief)

#### [NEW] [agents/llm_provider.py](file:///C:/Users/yugan/.gemini/antigravity/scratch/chakravyuh/backend/app/agents/llm_provider.py)
- Reads comma-separated `GROQ_API_KEYS` from env
- Thread-safe round-robin rotator — each call picks the next key
- On `RateLimitError`, automatically retries with the next key (up to N keys)
- Exposes `get_llm() -> ChatGroq` function used by marketer & auditor

#### [NEW] [agents/graph.py](file:///C:/Users/yugan/.gemini/antigravity/scratch/chakravyuh/backend/app/agents/graph.py)
- LangGraph `StateGraph` wiring the marketer and auditor nodes
- `generate_scenario` node → calls marketer
- `generate_report` node → calls auditor
- Conditional edges based on `game_over` flag

---

### API Layer

#### [NEW] [main.py](file:///C:/Users/yugan/.gemini/antigravity/scratch/chakravyuh/backend/app/main.py)
- `POST /api/start` — generate session, persona, initial scenario → return `GameState`
- `POST /api/action` — accept `ActionRequest`, run math engine, advance month, generate next scenario or post-mortem → return `GameState`
- CORS middleware enabled for `*` (hackathon convenience)
- Health check at `GET /`

#### [NEW] [app/\_\_init\_\_.py](file:///C:/Users/yugan/.gemini/antigravity/scratch/chakravyuh/backend/app/__init__.py)
Empty init.

---

## Verification Plan

### Automated Tests
1. **Pydantic validation test** — run a quick Python script that instantiates all models with sample data and asserts no `ValidationError`:
   ```
   cd C:\Users\yugan\.gemini\antigravity\scratch\chakravyuh\backend
   python -c "from app.models import *; print('All models OK')"
   ```
2. **Docker build** — confirm the image builds without errors:
   ```
   docker build -t chakravyuh-backend .
   ```
3. **API smoke test** (after container is up):
   ```
   curl -X POST http://localhost:8000/api/start
   ```
   Expect HTTP 200 with a valid `GameState` JSON body.

### Manual Verification
- The user should set `GROQ_API_KEYS` in a `.env` file, then run `docker compose up` and hit `/api/start` from their browser or Postman to see a full game initialization response.

> [!IMPORTANT]
> A `GROQ_API_KEYS` environment variable (comma-separated list of Groq API keys) is required. The system rotates through keys round-robin to avoid rate limits. Example `.env`:
> ```
> GROQ_API_KEYS=gsk_key1,gsk_key2,gsk_key3
> ```
