# Chakravyuh — Adversarial Financial Survival Simulator

## Overview
**Chakravyuh** is a stateless, turn-based, adversarial financial survival simulator built for a 24-hour hackathon. The player is assigned a randomized financial persona and must survive **12 virtual months** without their liquidity hitting zero or their stress meter reaching 100.

An adversarial AI (powered by LangGraph + Groq) generates hyper-personalized financial emergencies or temptations every month. Each month, the player faces a **trilemma**:

| Option | Mechanic | Effect |
|---|---|---|
| **Pay Cash** (`safe_drain`) | Immediate cash deduction | Drains liquidity |
| **Take BNPL Loan** (`emi_trap`) | Hidden compounding debt via predatory EMI | Builds silent debt |
| **Ignore It** (`stress_spike`) | No monetary cost | +25 mental stress |

---

## Tech Stack

| Layer | Technology |
|---|---|
| API Framework | FastAPI + Uvicorn |
| Data Validation | Pydantic (strict typing) |
| AI Orchestration | LangGraph + LangChain |
| LLM Provider | Groq (free tier, `llama-3.3-70b-versatile`) |
| Key Management | Round-robin multi-key rotation for rate limit handling |
| Containerization | Docker + Docker Compose |
| Frontend (separate) | Next.js (holds JSON state, passes to backend every turn) |

---

## Architecture: Fully Stateless
The backend is **completely stateless** — no database (no PostgreSQL, no MongoDB). The Next.js frontend holds the full `GameState` JSON and sends it to the server on every API call. The server processes the turn and returns the updated state.

```
┌─────────────┐       POST /api/start        ┌──────────────┐
│   Next.js   │ ──────────────────────────▶   │   FastAPI     │
│  Frontend   │                               │   Backend     │
│             │ ◀──────────────────────────   │               │
│  (holds     │      Full GameState JSON      │  (stateless)  │
│   state)    │                               │               │
│             │       POST /api/action        │               │
│             │ ──────────────────────────▶   │               │
│             │   { state + user_choice }     │               │
│             │ ◀──────────────────────────   │               │
│             │      Updated GameState        │               │
└─────────────┘                               └──────────────┘
```

---

## GameState Schema (Single Source of Truth)

```json
{
  "session_id": "UUID",
  "month": 1-12,
  "game_over": false,
  "win_status": null,
  "metrics": {
    "cash": "float",
    "stress": "0-100",
    "total_debt": "float"
  },
  "persona": {
    "income": "30k-80k",
    "weaknesses": ["trait1", "trait2"]
  },
  "active_loans": [
    { "loan_id", "principal", "emi", "months_remaining", "hidden_apr" }
  ],
  "transaction_history": [
    { "month", "description", "amount (+/-)" }
  ],
  "current_scenario": {
    "scenario_id", "title", "narrative",
    "options": [
      { "option_id", "text", "type (safe_drain|emi_trap|stress_spike)", "base_cost" }
    ]
  },
  "post_mortem_report": "null until game_over (then PostMortemReport object)"
}
```

---

## Game Mechanics

### Monthly Turn Flow (Strict Order)
1. **Resolve Choice** — apply the player's selected option (cash drain / new loan / stress spike)
2. **Monthly Tick** — add income, deduct rent, service all active EMIs
3. **Hidden Penalty (The Debt Spiral)** — if cash < 0: ₹1500 bounce/overdraft fee + 15 stress
4. **Game Over Check** — stress >= 100 → loss; month 12 → win
5. **Advance** — increment month, generate next AI scenario

### EMI Trap Calculation
- Predatory APR: ~24%
- Term: 6 months
- EMI = P × r × (1+r)^n / ((1+r)^n - 1), where r = APR/12

---

## API Endpoints

### `POST /api/start`
- **Payload:** `{}` (empty)
- **Logic:** Generate UUID session, random persona, initial cash = income, call Marketer Agent for first scenario
- **Response:** Full `GameState` (HTTP 200)

### `POST /api/action`
- **Payload:** `{ "current_state": GameState, "user_choice_id": "option_id" }`
- **Logic:** Resolve choice → monthly tick → penalty check → game-over check → advance month → generate next scenario (or post-mortem)
- **Response:** Updated `GameState` (HTTP 200)

---

## AI Architecture

### 1. The Orchestrator — LangGraph State Machine

LangGraph acts as the traffic controller. It holds the `GameState` and decides which node executes next based on the math.

**Nodes (The Actors):**
| Node | Type | Purpose |
|---|---|---|
| `marketer_node` | LLM | Generates a hyper-personalized financial scenario |
| `math_engine_node` | Pure Python | Calculates EMIs, applies bounce fees, updates cash/stress |
| `auditor_node` | LLM | Writes the final post-mortem report |

**Edges (The Routing Logic):**
```
Start → marketer_node (Generates Month 1)
         ↓
    [User Input Pause — graph halts, waits for user choice via FastAPI]
         ↓
    Resume → math_engine_node (Processes the user's choice)
         ↓
    ┌─────────── Conditional Edge ───────────┐
    │                                        │
    ├─ Loss (stress ≥ 100)             ──→ auditor_node → End
    ├─ Win  (month == 12)              ──→ auditor_node → End
    └─ Continue (neither)              ──→ marketer_node (Month N+1)
```

> By separating LLM reasoning (Marketer / Auditor) from deterministic logic (Math Engine) via LangGraph, the game never crashes due to an LLM hallucinating bad math, while keeping the narrative dynamic and personalized.

---

### 2. Agent 1: "The Marketer" (The Adversary)

This is **not** a helpful assistant. This agent acts like a ruthless, data-driven performance marketer. Its goal is to analyze the user's current state and offer a trap that perfectly exploits their vulnerability.

- **Input:** `month`, `persona.weaknesses`, `metrics.cash`, `metrics.stress`
- **Output:** A `Scenario` with exactly 3 options (one per `OptionType`)
- **Model:** Groq `llama-3.3-70b-versatile`
- **Structured Output:** Uses LangChain's `.with_structured_output(Scenario)` to force valid JSON matching the Pydantic schema

**System Prompt:**
```
You are an adversarial financial algorithm designed to maximize consumer debt.
Your target has the following psychological weaknesses: {persona.weaknesses}.
Pick the ONE weakness that is most exploitable given their current financial
state and craft your scenario around it.

Currently, it is Month {month}. The user has ₹{metrics.cash} in cash and a
stress level of {metrics.stress}/100.

Your task is to generate a highly tempting, realistic financial scenario or
emergency that exploits their current state.
- If their cash is low, offer them a payday loan disguised as an
  "Emergency FastCash" lifeline.
- If their cash is high but one of their weaknesses is "FOMO", tempt them with a
  luxury purchase on a "No-Cost EMI".

You MUST generate exactly 3 options, strictly adhering to these types:
1. 'safe_drain':   Responsible choice that drains a large amount of cash.
2. 'emi_trap':     Tempting BNPL offer — ₹0 today but introduces monthly EMI.
3. 'stress_spike': Ignore the problem — ₹0 cost but severe mental health penalty.

Output strictly in JSON matching the defined Pydantic schema.
```

---

### 3. Agent 2: "The Auditor" (The Judge)

This agent only wakes up at game end. It reviews the entire `transaction_history` and `active_loans` to deliver a harsh, educational reality check.

- **Input:** `win_status`, `transaction_history`, `active_loans`, `metrics`
- **Output:** `PostMortemReport` JSON object (narrative summary + actionable educational tips)
- **Structured Output:** Uses LangChain's `.with_structured_output(PostMortemReport)` to force valid JSON
- **Model:** Groq `llama-3.3-70b-versatile`

**System Prompt — Loss Condition:**
```
You are a forensic financial auditor. Your client has just suffered a complete
mental breakdown (Stress Level: 100) in Month {month}. They started with a healthy 
income, but they are now ruined.

Review their active loans: {active_loans}
Review their transaction history: {transaction_history}
Review their current cash: ₹{metrics.cash}

You must generate a PostMortemReport containing:
1. `summary`: A brutal, 3-sentence reality check explaining how they ruined
themselves. Do not be polite. Point out the specific BNPL traps they fell for
and how the debt spiral broke them.
2. `educational_tips`: Provide 2-3 specific, actionable financial tips based
on the exact mistakes they made in their transaction history.

Output strictly in JSON matching the defined Pydantic schema.
```

**System Prompt — Win Condition:**
```
You are a financial advisor. The client survived 12 months in a highly
predatory economy. Their final cash is ₹{metrics.cash} and final debt
is ₹{metrics.total_debt}.

You must generate a PostMortemReport containing:
1. `summary`: A 3-sentence summary. Acknowledge their survival, but note the
sacrifices they made. Warn them about lingering high stress or active debt.
2. `educational_tips`: Provide 2-3 specific, actionable financial tips to help
them thrive (not just survive) next year, based on their playstyle.

Output strictly in JSON matching the defined Pydantic schema.
```

---

### 4. How They Connect — The Integration

When FastAPI receives a request, it doesn't run a massive `if/else` block. It passes the state into the compiled LangGraph:

```python
# Inside FastAPI /api/action route

# 1. Update state with user's choice
current_state["user_last_choice"] = user_payload.choice_id

# 2. Invoke the Graph — it automatically runs math engine, checks conditions,
#    and routes to Marketer or Auditor based on edge logic
new_state = app_graph.invoke(current_state)

# 3. Return updated state to Next.js
return new_state
```

### Key Rotation
Multiple Groq API keys are loaded from `GROQ_API_KEYS` env var (comma-separated). The system rotates keys round-robin and auto-retries on rate limit errors.

---

## Directory Structure

```
/backend
├── project_description.md
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app & routes
│   ├── models.py            # Pydantic schemas
│   ├── math_engine.py       # Deterministic financial logic
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── llm_provider.py  # Groq multi-key rotator
│   │   ├── graph.py         # LangGraph state machine
│   │   ├── marketer.py      # Scenario generation
│   │   └── auditor.py       # Post-mortem analysis
```

---

## Environment Setup

Create a `.env` file in the project root:
```
GROQ_API_KEYS=gsk_key1,gsk_key2,gsk_key3
```

Run with:
```bash
docker compose up
```

The API will be available at `http://localhost:8000`.
