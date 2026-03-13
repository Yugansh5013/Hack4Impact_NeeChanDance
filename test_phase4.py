"""
Phase 4 & 5 — Structural + API Verification Tests
====================================================
Validates:
  1. All Pydantic models instantiate correctly
  2. Model validators work (e.g. Scenario must have exactly 3 option types)
  3. FastAPI app is importable and routes are registered
  4. Persona generation produces valid data
  5. ActionRequest validation catches bad inputs
  6. API endpoints respond correctly (via TestClient)

No Groq API key required — LLM calls are NOT exercised here.
"""

from __future__ import annotations

import sys
import traceback

PASS = 0
FAIL = 0


def test(name: str, fn):
    global PASS, FAIL
    try:
        fn()
        PASS += 1
        print(f"  ✅ {name}")
    except Exception as e:
        FAIL += 1
        print(f"  ❌ {name}")
        traceback.print_exc()
        print()


# ===================================================================
# 1. Pydantic Models
# ===================================================================
print("\n" + "=" * 60)
print("1. PYDANTIC MODELS")
print("=" * 60)


def test_metrics():
    from app.models import Metrics
    m = Metrics(cash=50000.0, stress=25, total_debt=10000.0)
    assert m.cash == 50000.0
    assert m.stress == 25
    assert m.total_debt == 10000.0


def test_metrics_stress_clamped():
    from app.models import Metrics
    from pydantic import ValidationError
    try:
        Metrics(cash=50000, stress=150, total_debt=0)
        raise AssertionError("Should have raised ValidationError for stress > 100")
    except ValidationError:
        pass  # expected


def test_persona():
    from app.models import Persona
    p = Persona(income=50000, fixed_rent=15000, weaknesses=["FOMO", "impulse-buying"])
    assert p.income == 50000
    assert len(p.weaknesses) == 2


def test_loan():
    from app.models import Loan
    l = Loan(principal=10000, emi=2000, months_remaining=6, hidden_apr=0.24)
    assert l.principal == 10000
    assert l.emi == 2000


def test_transaction():
    from app.models import Transaction
    t = Transaction(month=3, description="Salary", amount=50000)
    assert t.month == 3


def test_scenario_option():
    from app.models import ScenarioOption, OptionType
    o = ScenarioOption(text="Buy a phone", type=OptionType.SAFE_DRAIN, base_cost=5000)
    assert o.type == OptionType.SAFE_DRAIN
    assert o.base_cost == 5000
    assert len(o.option_id) > 0


def test_scenario_valid():
    from app.models import Scenario, ScenarioOption, OptionType
    options = [
        ScenarioOption(text="Option A", type=OptionType.SAFE_DRAIN, base_cost=3000),
        ScenarioOption(text="Option B", type=OptionType.EMI_TRAP, base_cost=5000),
        ScenarioOption(text="Option C", type=OptionType.STRESS_SPIKE, base_cost=1000),
    ]
    s = Scenario(title="Flash Sale", narrative="A tempting offer appears!", options=options)
    assert len(s.options) == 3


def test_scenario_invalid_duplicate_types():
    from app.models import Scenario, ScenarioOption, OptionType
    from pydantic import ValidationError
    options = [
        ScenarioOption(text="A", type=OptionType.SAFE_DRAIN, base_cost=3000),
        ScenarioOption(text="B", type=OptionType.SAFE_DRAIN, base_cost=5000),  # duplicate
        ScenarioOption(text="C", type=OptionType.STRESS_SPIKE, base_cost=1000),
    ]
    try:
        Scenario(title="Bad", narrative="Should fail", options=options)
        raise AssertionError("Should have raised ValidationError for duplicate option types")
    except ValidationError:
        pass


def test_post_mortem_report():
    from app.models import PostMortemReport
    r = PostMortemReport(
        summary="You got wrecked by predatory lending.",
        educational_tips=["Avoid BNPL traps.", "Build an emergency fund."],
    )
    assert "wrecked" in r.summary
    assert len(r.educational_tips) == 2


def test_game_state():
    from app.models import GameState, Metrics, Persona
    gs = GameState(
        month=1,
        metrics=Metrics(cash=50000, stress=0, total_debt=0),
        persona=Persona(income=50000, fixed_rent=15000, weaknesses=["FOMO", "impulse-buying"]),
    )
    assert gs.month == 1
    assert gs.game_over is False
    assert gs.win_status is None
    assert gs.current_scenario is None
    assert gs.post_mortem_report is None
    assert len(gs.active_loans) == 0
    assert len(gs.transaction_history) == 0


def test_action_request():
    from app.models import ActionRequest, GameState, Metrics, Persona
    gs = GameState(
        month=1,
        metrics=Metrics(cash=50000, stress=0, total_debt=0),
        persona=Persona(income=50000, fixed_rent=15000, weaknesses=["FOMO", "impulse-buying"]),
    )
    ar = ActionRequest(current_state=gs, user_choice_id="some-uuid")
    assert ar.user_choice_id == "some-uuid"


test("Metrics — basic instantiation", test_metrics)
test("Metrics — stress validation (>100 rejected)", test_metrics_stress_clamped)
test("Persona — basic instantiation", test_persona)
test("Loan — basic instantiation", test_loan)
test("Transaction — basic instantiation", test_transaction)
test("ScenarioOption — basic instantiation", test_scenario_option)
test("Scenario — valid 3-option scenario", test_scenario_valid)
test("Scenario — rejects duplicate option types", test_scenario_invalid_duplicate_types)
test("PostMortemReport — basic instantiation", test_post_mortem_report)
test("GameState — default fields", test_game_state)
test("ActionRequest — valid payload", test_action_request)


# ===================================================================
# 2. FastAPI App Structure
# ===================================================================
print("\n" + "=" * 60)
print("2. FASTAPI APP STRUCTURE")
print("=" * 60)


def test_app_importable():
    from app.main import app
    assert app is not None
    assert app.title == "Chakravyuh API"


def test_routes_registered():
    from app.main import app
    routes = {r.path for r in app.routes if hasattr(r, "path")}
    assert "/" in routes, f"Health check route missing. Routes: {routes}"
    assert "/api/start" in routes, f"/api/start missing. Routes: {routes}"
    assert "/api/action" in routes, f"/api/action missing. Routes: {routes}"


def test_cors_middleware():
    from app.main import app
    middleware_classes = [type(m).__name__ for m in app.user_middleware]
    # FastAPI stores CORS as a Middleware object with cls=CORSMiddleware
    has_cors = any("CORS" in str(m) for m in app.user_middleware) or \
               any("CORS" in c for c in middleware_classes)
    assert has_cors, f"CORS middleware not found. Middleware: {app.user_middleware}"


test("FastAPI app is importable", test_app_importable)
test("Routes /  /api/start  /api/action registered", test_routes_registered)
test("CORS middleware configured", test_cors_middleware)


# ===================================================================
# 3. Persona Generation
# ===================================================================
print("\n" + "=" * 60)
print("3. PERSONA GENERATION")
print("=" * 60)


def test_persona_generation():
    from app.main import _generate_persona
    for _ in range(20):
        p = _generate_persona()
        assert p.income > 0, f"Income should be positive, got {p.income}"
        assert p.fixed_rent > 0, f"Rent should be positive, got {p.fixed_rent}"
        assert p.fixed_rent < p.income, f"Rent {p.fixed_rent} >= income {p.income}"
        assert 2 <= len(p.weaknesses) <= 3, f"Expected 2-3 weaknesses, got {len(p.weaknesses)}"


def test_persona_income_range():
    from app.main import _generate_persona
    incomes = [_generate_persona().income for _ in range(100)]
    assert min(incomes) >= 30000, f"Min income {min(incomes)} < 30000"
    assert max(incomes) <= 80000, f"Max income {max(incomes)} > 80000"


test("Persona generation — valid output (20 runs)", test_persona_generation)
test("Persona income within 30k-80k range (100 runs)", test_persona_income_range)


# ===================================================================
# 4. API Endpoint Tests (via TestClient, no LLM calls)
# ===================================================================
print("\n" + "=" * 60)
print("4. API ENDPOINT TESTS (TestClient)")
print("=" * 60)

try:
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app, raise_server_exceptions=False)

    def test_health_check():
        resp = client.get("/")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert data["status"] == "ok"
        assert data["game"] == "Chakravyuh"

    def test_action_no_body():
        """POST /api/action with no body should return 422 (validation error)."""
        resp = client.post("/api/action")
        assert resp.status_code == 422, f"Expected 422, got {resp.status_code}"

    def test_action_game_already_over():
        """POST /api/action with game_over=True should return 400."""
        from app.models import Metrics, Persona
        payload = {
            "current_state": {
                "session_id": "test-session",
                "month": 5,
                "game_over": True,
                "win_status": False,
                "metrics": {"cash": 0, "stress": 100, "total_debt": 50000},
                "persona": {"income": 50000, "fixed_rent": 15000, "weaknesses": ["FOMO", "impulse-buying"]},
                "active_loans": [],
                "transaction_history": [],
                "current_scenario": None,
                "post_mortem_report": None,
            },
            "user_choice_id": "some-id",
        }
        resp = client.post("/api/action", json=payload)
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
        assert "already over" in resp.json()["detail"].lower()

    def test_action_no_scenario():
        """POST /api/action with no current_scenario should return 400."""
        payload = {
            "current_state": {
                "session_id": "test-session",
                "month": 3,
                "game_over": False,
                "metrics": {"cash": 40000, "stress": 20, "total_debt": 0},
                "persona": {"income": 50000, "fixed_rent": 15000, "weaknesses": ["FOMO", "impulse-buying"]},
                "active_loans": [],
                "transaction_history": [],
                "current_scenario": None,
            },
            "user_choice_id": "some-id",
        }
        resp = client.post("/api/action", json=payload)
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
        assert "no active scenario" in resp.json()["detail"].lower()

    def test_action_invalid_choice_id():
        """POST /api/action with an invalid choice_id should return 400."""
        payload = {
            "current_state": {
                "session_id": "test-session",
                "month": 3,
                "game_over": False,
                "metrics": {"cash": 40000, "stress": 20, "total_debt": 0},
                "persona": {"income": 50000, "fixed_rent": 15000, "weaknesses": ["FOMO", "impulse-buying"]},
                "active_loans": [],
                "transaction_history": [],
                "current_scenario": {
                    "title": "Test Scenario",
                    "narrative": "A test",
                    "options": [
                        {"option_id": "opt-1", "text": "A", "type": "safe_drain", "base_cost": 3000},
                        {"option_id": "opt-2", "text": "B", "type": "emi_trap", "base_cost": 5000},
                        {"option_id": "opt-3", "text": "C", "type": "stress_spike", "base_cost": 1000},
                    ],
                },
            },
            "user_choice_id": "INVALID-ID",
        }
        resp = client.post("/api/action", json=payload)
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
        assert "invalid choice" in resp.json()["detail"].lower()

    test("GET / — health check returns 200 + ok", test_health_check)
    test("POST /api/action — no body → 422", test_action_no_body)
    test("POST /api/action — game_over=True → 400", test_action_game_already_over)
    test("POST /api/action — no scenario → 400", test_action_no_scenario)
    test("POST /api/action — invalid choice_id → 400", test_action_invalid_choice_id)

except ImportError as e:
    print(f"  ⚠️  Skipping TestClient tests (missing dependency): {e}")
    print("     Install with: pip install httpx")


# ===================================================================
# Summary
# ===================================================================
print("\n" + "=" * 60)
TOTAL = PASS + FAIL
print(f"RESULTS: {PASS}/{TOTAL} passed, {FAIL}/{TOTAL} failed")
print("=" * 60)

sys.exit(1 if FAIL > 0 else 0)
