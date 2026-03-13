"""
Chakravyuh — FastAPI Application
==================================
Stateless API layer.  The Next.js frontend holds the full GameState
JSON and passes it on every request.  The backend processes the turn
via LangGraph + Math Engine and returns the updated state.

Endpoints
---------
GET  /              Health check
POST /api/start     Begin a new game — returns initial GameState
POST /api/action    Process a player's choice — returns updated GameState
"""

from __future__ import annotations

import random
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.models import (
    ActionRequest,
    GameState,
    Metrics,
    Persona,
)
from app.agents.graph import start_graph, action_graph

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Chakravyuh API",
    description="Adversarial Financial Survival Simulator",
    version="1.0.0",
)

# CORS — wide open for hackathon convenience
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Persona Generation
# ---------------------------------------------------------------------------

WEAKNESS_POOL: list[str] = [
    "FOMO",
    "impulse-buying",
    "retail-therapy",
    "gadget-obsession",
    "lifestyle-inflation",
    "social-comparison",
    "instant-gratification",
    "emotional-spending",
    "subscription-hoarding",
    "deal-hunting",
]


def _generate_persona() -> Persona:
    """Create a randomised financial persona for a new game."""
    income = round(random.uniform(30000, 80000), -3)   # round to nearest 1000
    fixed_rent = round(income * random.uniform(0.25, 0.40), -2)  # 25-40% of income
    weaknesses = random.sample(WEAKNESS_POOL, k=random.randint(2, 3))
    return Persona(income=income, fixed_rent=fixed_rent, weaknesses=weaknesses)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/")
async def health_check():
    """Simple liveness probe."""
    return {"status": "ok", "game": "Chakravyuh"}


@app.post("/api/start", response_model=GameState)
async def start_game():
    """
    Begin a new game.

    - Generates a random persona
    - Sets initial cash = persona.income (one month's salary in the bank)
    - Invokes the LangGraph start_graph to generate the Month 1 scenario
    - Returns the full GameState
    """
    persona = _generate_persona()

    initial_state = GameState(
        session_id=str(uuid.uuid4()),
        month=1,
        metrics=Metrics(
            cash=persona.income,       # start with one month's salary
            stress=0,
            total_debt=0.0,
        ),
        persona=persona,
    )

    # Run the start graph — generates the first scenario
    result = start_graph.invoke({"game_state": initial_state})
    game_state: GameState = result["game_state"]

    return game_state


@app.post("/api/action", response_model=GameState)
async def take_action(request: ActionRequest):
    """
    Process a player's choice.

    - Validates the choice exists in the current scenario
    - Invokes the LangGraph action_graph which:
        1. Runs the math engine (resolve choice + monthly tick + penalties)
        2. Checks for game-over conditions
        3. Routes to Marketer (next scenario) or Auditor (post-mortem)
    - Returns the updated GameState
    """
    state = request.current_state
    choice_id = request.user_choice_id

    # Validate that the game is not already over
    if state.game_over:
        raise HTTPException(
            status_code=400,
            detail="Game is already over. Start a new game with POST /api/start.",
        )

    # Validate that a scenario exists
    if state.current_scenario is None:
        raise HTTPException(
            status_code=400,
            detail="No active scenario. The game state may be corrupted.",
        )

    # Validate the choice_id exists in the scenario options
    valid_ids = [opt.option_id for opt in state.current_scenario.options]
    if choice_id not in valid_ids:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid choice '{choice_id}'. Valid options: {valid_ids}",
        )

    # Run the action graph
    result = action_graph.invoke({
        "game_state": state,
        "user_choice_id": choice_id,
    })
    updated_state: GameState = result["game_state"]

    return updated_state
