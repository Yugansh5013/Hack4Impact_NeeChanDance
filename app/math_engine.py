"""
Chakravyuh — Deterministic Financial Math Engine
==================================================
Pure functions for all game-logic calculations.
NO LLM calls — every result is reproducible and testable.

Monthly Turn Flow (Strict Order):
    1. Resolve Choice  — apply the player's selected option
    2. Monthly Tick    — add income, deduct rent, service all active EMIs
    3. Hidden Penalty  — if cash < 0: ₹1500 bounce fee + 15 stress
    4. Game Over Check — stress >= 100 → loss; month == 12 → win
"""

from __future__ import annotations

import copy
from typing import Tuple

from app.models import (
    GameState,
    Loan,
    Metrics,
    OptionType,
    ScenarioOption,
    Transaction,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PREDATORY_APR: float = 0.24          # 24 % annual
LOAN_TERM_MONTHS: int = 6            # 6-month repayment window
STRESS_SPIKE_AMOUNT: int = 25        # stress added when ignoring a problem
BOUNCE_FEE: float = 1500.0           # overdraft / bounce penalty (₹)
BOUNCE_STRESS: int = 15              # stress added on cash < 0
MAX_STRESS: int = 100
FINAL_MONTH: int = 12


# ---------------------------------------------------------------------------
# EMI Helpers
# ---------------------------------------------------------------------------

def calculate_emi(principal: float, apr: float = PREDATORY_APR,
                  term_months: int = LOAN_TERM_MONTHS) -> float:
    """
    Standard reducing-balance EMI formula:
        EMI = P × r × (1+r)^n / ((1+r)^n − 1)

    where r = APR / 12 (monthly rate), n = term in months.

    Returns the fixed monthly instalment amount (₹).
    """
    if principal <= 0:
        return 0.0
    if term_months <= 0:
        return principal  # immediate repayment
    r = apr / 12.0
    if r == 0:
        return principal / term_months
    factor = (1 + r) ** term_months
    return round(principal * r * factor / (factor - 1), 2)


# ---------------------------------------------------------------------------
# Step 1 — Resolve Choice
# ---------------------------------------------------------------------------

def apply_choice(state: GameState, chosen_option: ScenarioOption) -> GameState:
    """
    Apply the player's selected option to the game state.

    • safe_drain   → immediate cash deduction of `base_cost`
    • emi_trap     → no cash impact today; creates a new Loan with predatory EMI
    • stress_spike → no cash impact; adds +25 stress (clamped to 100)

    Returns a **new** GameState with the choice resolved and a Transaction logged.
    """
    state = state.model_copy(deep=True)
    month = state.month

    if chosen_option.type == OptionType.SAFE_DRAIN:
        # Direct cash drain
        state.metrics.cash = round(state.metrics.cash - chosen_option.base_cost, 2)
        state.transaction_history.append(
            Transaction(
                month=month,
                description=f"[PAID] {chosen_option.text}",
                amount=round(-chosen_option.base_cost, 2),
            )
        )

    elif chosen_option.type == OptionType.EMI_TRAP:
        # Create new predatory loan — ₹0 today, but EMI starts next tick
        emi = calculate_emi(chosen_option.base_cost)
        new_loan = Loan(
            principal=chosen_option.base_cost,
            emi=emi,
            months_remaining=LOAN_TERM_MONTHS,
            hidden_apr=PREDATORY_APR,
        )
        state.active_loans.append(new_loan)
        state.metrics.total_debt = round(
            state.metrics.total_debt + chosen_option.base_cost, 2
        )
        state.transaction_history.append(
            Transaction(
                month=month,
                description=f"[BNPL LOAN] {chosen_option.text} — EMI ₹{emi}/mo for {LOAN_TERM_MONTHS} months",
                amount=0.0,  # no cash impact today
            )
        )

    elif chosen_option.type == OptionType.STRESS_SPIKE:
        # No monetary cost; stress penalty
        state.metrics.stress = min(
            state.metrics.stress + STRESS_SPIKE_AMOUNT, MAX_STRESS
        )
        state.transaction_history.append(
            Transaction(
                month=month,
                description=f"[IGNORED] {chosen_option.text} — stress +{STRESS_SPIKE_AMOUNT}",
                amount=0.0,
            )
        )

    return state


# ---------------------------------------------------------------------------
# Step 2 — Monthly Tick (income, rent, EMI servicing)
# ---------------------------------------------------------------------------

def monthly_tick(state: GameState) -> GameState:
    """
    Execute the monthly financial cycle:
        1. Credit income
        2. Deduct fixed rent
        3. Service every active loan (deduct EMI, decrement months_remaining)
        4. Remove fully-repaid loans

    Returns a new GameState.
    """
    state = state.model_copy(deep=True)
    month = state.month

    # --- 1. Income ---
    state.metrics.cash = round(state.metrics.cash + state.persona.income, 2)
    state.transaction_history.append(
        Transaction(month=month, description="[INCOME] Monthly salary", amount=state.persona.income)
    )

    # --- 2. Rent ---
    state.metrics.cash = round(state.metrics.cash - state.persona.fixed_rent, 2)
    state.transaction_history.append(
        Transaction(
            month=month,
            description="[RENT] Monthly fixed obligation",
            amount=round(-state.persona.fixed_rent, 2),
        )
    )

    # --- 3. Service EMIs ---
    surviving_loans: list[Loan] = []
    for loan in state.active_loans:
        if loan.months_remaining <= 0:
            continue  # already paid off — skip
        state.metrics.cash = round(state.metrics.cash - loan.emi, 2)
        state.transaction_history.append(
            Transaction(
                month=month,
                description=f"[EMI] Loan {loan.loan_id[:8]}… — ₹{loan.emi}",
                amount=round(-loan.emi, 2),
            )
        )
        # Reduce outstanding debt tracker
        state.metrics.total_debt = round(
            max(state.metrics.total_debt - loan.emi, 0), 2
        )
        remaining = loan.months_remaining - 1
        if remaining > 0:
            surviving_loans.append(
                loan.model_copy(update={"months_remaining": remaining})
            )
        # else: loan fully repaid — drop it

    state.active_loans = surviving_loans

    return state


# ---------------------------------------------------------------------------
# Step 3 — Hidden Penalty (Bounce / Overdraft)
# ---------------------------------------------------------------------------

def apply_penalty(state: GameState) -> GameState:
    """
    The Debt Spiral penalty:
        If cash < 0 after the monthly tick, the player is hit with:
            • ₹1,500 bounce / overdraft fee
            • +15 stress

    Returns a new GameState.
    """
    state = state.model_copy(deep=True)

    if state.metrics.cash < 0:
        state.metrics.cash = round(state.metrics.cash - BOUNCE_FEE, 2)
        state.metrics.stress = min(state.metrics.stress + BOUNCE_STRESS, MAX_STRESS)
        state.transaction_history.append(
            Transaction(
                month=state.month,
                description=f"[PENALTY] Overdraft bounce fee — ₹{BOUNCE_FEE} + stress +{BOUNCE_STRESS}",
                amount=round(-BOUNCE_FEE, 2),
            )
        )

    return state


# ---------------------------------------------------------------------------
# Step 4 — Game-Over Check
# ---------------------------------------------------------------------------

def check_game_over(state: GameState) -> GameState:
    """
    Evaluate termination conditions:
        • stress >= 100  → game_over=True, win_status=False  (loss)
        • month == 12    → game_over=True, win_status=True   (win)
        • otherwise      → game continues

    Returns a new GameState with `game_over` and `win_status` set.
    """
    state = state.model_copy(deep=True)

    if state.metrics.stress >= MAX_STRESS:
        state.game_over = True
        state.win_status = False  # loss — stress breakdown
    elif state.month >= FINAL_MONTH:
        state.game_over = True
        state.win_status = True   # survived all 12 months
    # else: game continues — no change

    return state


# ---------------------------------------------------------------------------
# Full Turn Pipeline
# ---------------------------------------------------------------------------

def process_turn(state: GameState, chosen_option: ScenarioOption) -> GameState:
    """
    Execute the complete turn pipeline in strict order:
        1. Resolve choice
        2. Monthly tick (income → rent → EMI servicing)
        3. Hidden penalty (bounce fee if cash < 0)
        4. Game-over check

    This does NOT advance the month — that is done by the caller
    (the API layer / LangGraph orchestrator) after optionally generating
    the next scenario.

    Returns the fully-updated GameState.
    """
    state = apply_choice(state, chosen_option)
    state = monthly_tick(state)
    state = apply_penalty(state)
    state = check_game_over(state)

    return state
