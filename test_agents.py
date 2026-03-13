"""
Chakravyuh — Phase 3 Integration Tests
========================================
Two test tiers:
  1. STRUCTURAL  (no API key) — graph topology, state flow, node wiring
  2. LIVE        (needs GROQ_API_KEYS in .env) — full LLM round-trip

Run:
    python test_agents.py              # structural only (always safe)
    python test_agents.py --live       # structural + live LLM calls
"""

from __future__ import annotations

import os
import sys
import json
import uuid

# ── Ensure we can import even without a .env ──
# Set a dummy key so llm_provider doesn't crash during structural tests
if "GROQ_API_KEYS" not in os.environ:
    os.environ["GROQ_API_KEYS"] = "dummy_structural_test_key"

from app.models import (
    GameState, Metrics, Persona, Loan, Transaction,
    Scenario, ScenarioOption, PostMortemReport, OptionType,
)
from app.math_engine import process_turn, calculate_emi
from app.agents.graph import (
    start_graph, action_graph,
    scenario_node, action_node, report_node,
    after_action_router, GraphState,
)


# ═══════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def make_test_state(month: int = 1, cash: float = 50000.0,
                    stress: int = 0) -> GameState:
    """Build a minimal valid GameState for testing."""
    return GameState(
        session_id=str(uuid.uuid4()),
        month=month,
        metrics=Metrics(cash=cash, stress=stress, total_debt=0.0),
        persona=Persona(
            income=40000.0,
            fixed_rent=12000.0,
            weaknesses=["FOMO", "impulse-buying"],
        ),
    )


def make_test_scenario(cash: float = 15000.0) -> Scenario:
    """Build a valid Scenario with 3 options."""
    return Scenario(
        title="Test Scenario",
        narrative="A test emergency.",
        options=[
            ScenarioOption(
                text="Pay cash now",
                type=OptionType.SAFE_DRAIN,
                base_cost=cash,
            ),
            ScenarioOption(
                text="Take No-Cost EMI",
                type=OptionType.EMI_TRAP,
                base_cost=10000.0,
            ),
            ScenarioOption(
                text="Ignore it",
                type=OptionType.STRESS_SPIKE,
                base_cost=0.0,
            ),
        ],
    )


PASS = "[PASS]"
FAIL = "[FAIL]"


def check(name: str, condition: bool, detail: str = ""):
    status = PASS if condition else FAIL
    print(f"  {status}  {name}" + (f"  ({detail})" if detail else ""))
    if not condition:
        raise AssertionError(f"Test failed: {name} — {detail}")


# ═══════════════════════════════════════════════════════════════════════════
# TIER 1: STRUCTURAL TESTS  (no API key needed)
# ═══════════════════════════════════════════════════════════════════════════

def test_graph_topology():
    """Verify both graphs have the expected node names."""
    print("\n── Graph Topology ──")

    start_nodes = set(start_graph.nodes.keys()) - {"__start__"}
    check("start_graph has scenario_node", "scenario_node" in start_nodes,
          f"nodes: {start_nodes}")

    action_nodes = set(action_graph.nodes.keys()) - {"__start__"}
    expected = {"action_node", "report_node", "scenario_node"}
    check("action_graph has all 3 nodes", expected.issubset(action_nodes),
          f"nodes: {action_nodes}")


def test_router_logic():
    """Verify the conditional edge routes correctly."""
    print("\n── Router Logic ──")

    # Game continues
    gs_continue = make_test_state(month=3, cash=30000, stress=40)
    route = after_action_router({"game_state": gs_continue})
    check("continue → scenario_node", route == "scenario_node", f"got: {route}")

    # Loss (stress >= 100)
    gs_loss = make_test_state(month=5, cash=10000, stress=100)
    gs_loss = gs_loss.model_copy(update={"game_over": True, "win_status": False})
    route = after_action_router({"game_state": gs_loss})
    check("loss → report_node", route == "report_node", f"got: {route}")

    # Win (month 12)
    gs_win = make_test_state(month=12, cash=20000, stress=50)
    gs_win = gs_win.model_copy(update={"game_over": True, "win_status": True})
    route = after_action_router({"game_state": gs_win})
    check("win → report_node", route == "report_node", f"got: {route}")


def test_action_node_safe_drain():
    """Verify action_node correctly processes a safe_drain choice."""
    print("\n── Action Node: safe_drain ──")

    gs = make_test_state(month=1, cash=50000)
    scenario = make_test_scenario(cash=15000)
    gs = gs.model_copy(update={"current_scenario": scenario})

    safe_opt = [o for o in scenario.options if o.type == OptionType.SAFE_DRAIN][0]

    result = action_node({
        "game_state": gs,
        "user_choice_id": safe_opt.option_id,
    })
    new_gs: GameState = result["game_state"]

    # After safe_drain(15000) + income(40000) - rent(12000) = 63000
    expected = 50000 - 15000 + 40000 - 12000
    check("cash correct after safe_drain + tick", new_gs.metrics.cash == expected,
          f"expected {expected}, got {new_gs.metrics.cash}")
    check("month advanced", new_gs.month == 2, f"month: {new_gs.month}")
    check("game not over", not new_gs.game_over)
    check("scenario cleared", new_gs.current_scenario is None)
    check("transactions logged", len(new_gs.transaction_history) >= 3,
          f"count: {len(new_gs.transaction_history)}")


def test_action_node_emi_trap():
    """Verify action_node correctly processes an emi_trap choice."""
    print("\n── Action Node: emi_trap ──")

    gs = make_test_state(month=1, cash=50000)
    scenario = make_test_scenario()
    gs = gs.model_copy(update={"current_scenario": scenario})

    emi_opt = [o for o in scenario.options if o.type == OptionType.EMI_TRAP][0]

    result = action_node({
        "game_state": gs,
        "user_choice_id": emi_opt.option_id,
    })
    new_gs: GameState = result["game_state"]

    check("loan created", len(new_gs.active_loans) == 1,
          f"loans: {len(new_gs.active_loans)}")

    # Cash after: 50000 (no drain) + 40000 (income) - 12000 (rent) - EMI
    emi = calculate_emi(10000)
    expected_cash = round(50000 + 40000 - 12000 - emi, 2)
    check("cash correct after emi_trap + tick", new_gs.metrics.cash == expected_cash,
          f"expected {expected_cash}, got {new_gs.metrics.cash}")


def test_action_node_stress_spike():
    """Verify action_node correctly processes a stress_spike choice."""
    print("\n── Action Node: stress_spike ──")

    gs = make_test_state(month=1, cash=50000, stress=0)
    scenario = make_test_scenario()
    gs = gs.model_copy(update={"current_scenario": scenario})

    stress_opt = [o for o in scenario.options if o.type == OptionType.STRESS_SPIKE][0]

    result = action_node({
        "game_state": gs,
        "user_choice_id": stress_opt.option_id,
    })
    new_gs: GameState = result["game_state"]

    check("stress increased by 25", new_gs.metrics.stress == 25,
          f"stress: {new_gs.metrics.stress}")
    # Cash after: 50000 + 40000 - 12000 = 78000
    check("cash unchanged by stress_spike", new_gs.metrics.cash == 78000.0,
          f"cash: {new_gs.metrics.cash}")


def test_action_node_invalid_choice():
    """Verify action_node raises on bad option_id."""
    print("\n── Action Node: invalid choice ──")

    gs = make_test_state()
    gs = gs.model_copy(update={"current_scenario": make_test_scenario()})

    try:
        action_node({"game_state": gs, "user_choice_id": "nonexistent_id"})
        check("raises on invalid id", False, "no exception raised")
    except ValueError as e:
        check("raises ValueError on invalid id", True, str(e)[:60])


def test_game_over_triggers_report_route():
    """Verify that a lethal stress spike routes to report_node."""
    print("\n── Game Over Routing ──")

    gs = make_test_state(month=5, cash=50000, stress=80)
    scenario = make_test_scenario()
    gs = gs.model_copy(update={"current_scenario": scenario})

    stress_opt = [o for o in scenario.options if o.type == OptionType.STRESS_SPIKE][0]
    result = action_node({
        "game_state": gs,
        "user_choice_id": stress_opt.option_id,
    })
    new_gs: GameState = result["game_state"]

    # stress 80 + 25 = 100 (but capped at 100) → game over
    check("stress hit 100", new_gs.metrics.stress >= 100,
          f"stress: {new_gs.metrics.stress}")
    check("game_over is True", new_gs.game_over)
    check("win_status is False", new_gs.win_status == False)

    route = after_action_router({"game_state": new_gs})
    check("routes to report_node", route == "report_node", f"route: {route}")


def test_month12_win_route():
    """Verify month 12 completion routes correctly."""
    print("\n── Month 12 Win ──")

    gs = make_test_state(month=12, cash=50000, stress=30)
    scenario = make_test_scenario()
    gs = gs.model_copy(update={"current_scenario": scenario})

    safe_opt = [o for o in scenario.options if o.type == OptionType.SAFE_DRAIN][0]
    result = action_node({
        "game_state": gs,
        "user_choice_id": safe_opt.option_id,
    })
    new_gs: GameState = result["game_state"]

    check("game_over is True at month 12", new_gs.game_over)
    check("win_status is True", new_gs.win_status == True)
    check("month stays 12 (no advance)", new_gs.month == 12,
          f"month: {new_gs.month}")

    route = after_action_router({"game_state": new_gs})
    check("routes to report_node", route == "report_node")


def run_structural_tests():
    print("=" * 60)
    print("  STRUCTURAL TESTS  (no API key required)")
    print("=" * 60)
    test_graph_topology()
    test_router_logic()
    test_action_node_safe_drain()
    test_action_node_emi_trap()
    test_action_node_stress_spike()
    test_action_node_invalid_choice()
    test_game_over_triggers_report_route()
    test_month12_win_route()
    print("\n" + "=" * 60)
    print(f"  {PASS}  ALL STRUCTURAL TESTS PASSED")
    print("=" * 60)


# ═══════════════════════════════════════════════════════════════════════════
# TIER 2: LIVE LLM TESTS  (requires GROQ_API_KEYS in .env)
# ═══════════════════════════════════════════════════════════════════════════

def test_live_marketer():
    """Hit the real Groq API to generate a scenario."""
    print("\n── Live Marketer Test ──")
    from app.agents.marketer import generate_scenario

    gs = make_test_state(month=3, cash=35000, stress=20)
    scenario = generate_scenario(gs)

    check("returned Scenario type", isinstance(scenario, Scenario))
    check("has 3 options", len(scenario.options) == 3)
    types = {o.type for o in scenario.options}
    check("all 3 option types present", types == {
        OptionType.SAFE_DRAIN, OptionType.EMI_TRAP, OptionType.STRESS_SPIKE
    }, f"types: {types}")
    check("title is non-empty", len(scenario.title) > 0, scenario.title[:50])
    check("narrative is non-empty", len(scenario.narrative) > 0,
          scenario.narrative[:50])
    print(f"\n  Generated scenario: \"{scenario.title}\"")
    for opt in scenario.options:
        print(f"     [{opt.type.value:12s}] Rs.{opt.base_cost:>8.0f}  {opt.text[:60]}")


def test_live_auditor_loss():
    """Hit the real Groq API to generate a loss report."""
    print("\n── Live Auditor Test (Loss) ──")
    from app.agents.auditor import generate_report

    gs = make_test_state(month=7, cash=-2000, stress=100)
    gs = gs.model_copy(update={
        "game_over": True,
        "win_status": False,
        "active_loans": [
            Loan(principal=15000, emi=2678.0, months_remaining=4, hidden_apr=0.24),
            Loan(principal=8000, emi=1428.0, months_remaining=5, hidden_apr=0.24),
        ],
        "transaction_history": [
            Transaction(month=1, description="[BNPL LOAN] Phone on EMI", amount=0),
            Transaction(month=2, description="[IGNORED] Medical bill", amount=0),
            Transaction(month=3, description="[BNPL LOAN] Laptop on EMI", amount=0),
            Transaction(month=5, description="[PENALTY] Overdraft bounce fee", amount=-1500),
        ],
    })

    report = generate_report(gs)

    check("returned PostMortemReport", isinstance(report, PostMortemReport))
    check("summary is non-empty", len(report.summary) > 0, report.summary[:80])
    check("has educational_tips", len(report.educational_tips) >= 1,
          f"count: {len(report.educational_tips)}")
    print(f"\n  Summary: {report.summary[:120]}...")
    for i, tip in enumerate(report.educational_tips, 1):
        print(f"  Tip {i}: {tip[:80]}")


def test_live_start_graph():
    """Full start_graph invocation — generates Month 1 scenario."""
    print("\n── Live Start Graph ──")

    gs = make_test_state(month=1, cash=50000)
    result = start_graph.invoke({"game_state": gs})
    new_gs: GameState = result["game_state"]

    check("scenario generated", new_gs.current_scenario is not None)
    check("3 options", len(new_gs.current_scenario.options) == 3)
    print(f"\n  Month 1 scenario: \"{new_gs.current_scenario.title}\"")


def test_live_full_turn():
    """Full action_graph invocation — play one complete turn."""
    print("\n── Live Full Turn (action_graph) ──")

    # First get a scenario
    gs = make_test_state(month=1, cash=50000)
    start_result = start_graph.invoke({"game_state": gs})
    gs_with_scenario: GameState = start_result["game_state"]

    # Pick the safe_drain option
    safe_opt = [o for o in gs_with_scenario.current_scenario.options
                if o.type == OptionType.SAFE_DRAIN][0]

    action_result = action_graph.invoke({
        "game_state": gs_with_scenario,
        "user_choice_id": safe_opt.option_id,
    })
    final_gs: GameState = action_result["game_state"]

    check("month advanced to 2", final_gs.month == 2, f"month: {final_gs.month}")
    check("new scenario generated", final_gs.current_scenario is not None)
    check("game not over", not final_gs.game_over)
    print(f"\n  Month 2 scenario: \"{final_gs.current_scenario.title}\"")
    print(f"  Cash: Rs.{final_gs.metrics.cash}  |  Stress: {final_gs.metrics.stress}")


def run_live_tests():
    from dotenv import load_dotenv
    load_dotenv(override=True)  # override the dummy key set during structural tests
    keys = os.getenv("GROQ_API_KEYS", "")
    if not keys or keys == "dummy_structural_test_key":
        print("\nSkipping live tests -- no GROQ_API_KEYS found in .env")
        print("   Create a .env file with: GROQ_API_KEYS=gsk_your_key_here")
        return False

    # Re-initialize the llm_provider module with real keys
    import app.agents.llm_provider as provider
    real_keys = [k.strip() for k in keys.split(",") if k.strip()]
    provider._keys = real_keys
    provider._index = 0
    print(f"\n  Loaded {len(real_keys)} API key(s) from .env")

    print("\n" + "=" * 60)
    print("  LIVE LLM TESTS  (calling Groq API)")
    print("=" * 60)
    test_live_marketer()
    test_live_auditor_loss()
    test_live_start_graph()
    test_live_full_turn()
    print("\n" + "=" * 60)
    print(f"  {PASS}  ALL LIVE TESTS PASSED")
    print("=" * 60)
    return True


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    run_structural_tests()

    if "--live" in sys.argv:
        run_live_tests()
    else:
        print("\nRun with --live to also test real LLM calls:")
        print("   python test_agents.py --live")
