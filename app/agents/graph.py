"""
Chakravyuh — LangGraph State Machine
=======================================
Wires the Marketer and Auditor nodes together with the Math Engine.
The graph is invoked by the FastAPI layer and returns the updated
game state.

Graph topology
--------------
::

    START
      │
      ▼
    generate_scenario  ← Marketer LLM creates month's scenario
      │
      ▼
    END  (return state with scenario; wait for player input)

    ----  (player submits choice via /api/action)  ----

    START
      │
      ▼
    process_action     ← Math Engine resolves choice + monthly tick
      │
      ├── game_over=True  ──▶  generate_report  ← Auditor LLM
      │                              │
      │                              ▼
      │                            END
      │
      └── game_over=False ──▶  generate_scenario  ← next month
                                     │
                                     ▼
                                   END
"""

from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import StateGraph, END

from app.models import GameState, ScenarioOption, OptionType
from app.math_engine import process_turn
from app.agents.marketer import generate_scenario as marketer_generate
from app.agents.auditor import generate_report as auditor_generate


# ---------------------------------------------------------------------------
# Graph State Schema
# ---------------------------------------------------------------------------

class GraphState(TypedDict, total=False):
    """State passed through the LangGraph nodes."""
    game_state: GameState
    user_choice_id: str | None  # option_id chosen by the player


# ---------------------------------------------------------------------------
# Node Functions
# ---------------------------------------------------------------------------

def scenario_node(state: GraphState) -> GraphState:
    """
    Call the Marketer agent to generate this month's scenario.
    Attaches the ``Scenario`` to ``game_state.current_scenario``.
    """
    gs: GameState = state["game_state"]
    scenario = marketer_generate(gs)
    gs = gs.model_copy(update={"current_scenario": scenario})
    return {"game_state": gs}


def action_node(state: GraphState) -> GraphState:
    """
    Resolve the player's choice via the deterministic Math Engine.

    1. Look up the chosen option from current_scenario
    2. Run ``process_turn`` (choice → tick → penalty → game-over check)
    3. If game is NOT over, advance the month
    4. Clear current_scenario (will be regenerated if game continues)
    """
    gs: GameState = state["game_state"]
    choice_id: str = state["user_choice_id"]

    # Find the chosen option
    chosen: ScenarioOption | None = None
    if gs.current_scenario:
        for opt in gs.current_scenario.options:
            if opt.option_id == choice_id:
                chosen = opt
                break

    if chosen is None:
        raise ValueError(
            f"Invalid user_choice_id '{choice_id}'. "
            f"Available options: "
            f"{[o.option_id for o in gs.current_scenario.options] if gs.current_scenario else '(no scenario)'}"
        )

    # Run the full turn pipeline
    gs = process_turn(gs, chosen)

    # Advance month if game continues
    if not gs.game_over:
        gs = gs.model_copy(update={"month": gs.month + 1})

    # Clear old scenario
    gs = gs.model_copy(update={"current_scenario": None})

    return {"game_state": gs}


def report_node(state: GraphState) -> GraphState:
    """
    Call the Auditor agent to generate the post-mortem report.
    Only invoked when ``game_over == True``.
    """
    gs: GameState = state["game_state"]
    report = auditor_generate(gs)
    gs = gs.model_copy(update={"post_mortem_report": report})
    return {"game_state": gs}


# ---------------------------------------------------------------------------
# Routing Logic
# ---------------------------------------------------------------------------

def after_action_router(state: GraphState) -> str:
    """
    Conditional edge after ``action_node``:
        • game_over → "report_node"  (Auditor writes post-mortem)
        • otherwise → "scenario_node" (Marketer generates next month)
    """
    gs: GameState = state["game_state"]
    if gs.game_over:
        return "report_node"
    return "scenario_node"


# ---------------------------------------------------------------------------
# Graph: Start Flow  (called by POST /api/start)
# ---------------------------------------------------------------------------

def _build_start_graph() -> StateGraph:
    """Graph that generates the initial scenario for Month 1."""
    g = StateGraph(GraphState)
    g.add_node("scenario_node", scenario_node)
    g.set_entry_point("scenario_node")
    g.add_edge("scenario_node", END)
    return g


# ---------------------------------------------------------------------------
# Graph: Action Flow  (called by POST /api/action)
# ---------------------------------------------------------------------------

def _build_action_graph() -> StateGraph:
    """
    Graph that processes a player action:
        action_node ──┬── game_over ──▶ report_node ──▶ END
                      └── continue  ──▶ scenario_node ──▶ END
    """
    g = StateGraph(GraphState)
    g.add_node("action_node", action_node)
    g.add_node("report_node", report_node)
    g.add_node("scenario_node", scenario_node)

    g.set_entry_point("action_node")
    g.add_conditional_edges("action_node", after_action_router)
    g.add_edge("report_node", END)
    g.add_edge("scenario_node", END)
    return g


# ---------------------------------------------------------------------------
# Compiled Graphs (module-level singletons)
# ---------------------------------------------------------------------------

start_graph = _build_start_graph().compile()
action_graph = _build_action_graph().compile()
