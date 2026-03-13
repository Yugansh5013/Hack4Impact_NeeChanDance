"""
Chakravyuh — Pydantic Schema Definitions
=========================================
All data models for the GameState, API requests, and sub-components.
These are the single source of truth shared between frontend and backend.
"""

from __future__ import annotations

import uuid
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class OptionType(str, Enum):
    """The three strict mechanical option types for every scenario."""
    SAFE_DRAIN = "safe_drain"
    EMI_TRAP = "emi_trap"
    STRESS_SPIKE = "stress_spike"


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------

class Metrics(BaseModel):
    """Player's financial & mental health gauges."""
    cash: float = Field(..., description="Current liquid cash (₹)")
    stress: int = Field(0, ge=0, le=100, description="Mental stress meter (0–100)")
    total_debt: float = Field(0.0, ge=0, description="Cumulative debt outstanding (₹)")


class Persona(BaseModel):
    """Randomized financial identity assigned at game start."""
    income: float = Field(..., gt=0, description="Monthly take-home income (₹)")
    fixed_rent: float = Field(..., gt=0, description="Monthly rent / fixed obligation (₹)")
    weaknesses: list[str] = Field(
        ...,
        min_length=2,
        max_length=3,
        description="Psychological weaknesses exploited by the Marketer AI",
    )


class Loan(BaseModel):
    """An active BNPL / predatory loan the player has taken."""
    loan_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for this loan",
    )
    principal: float = Field(..., gt=0, description="Original borrowed amount (₹)")
    emi: float = Field(..., gt=0, description="Monthly instalment amount (₹)")
    months_remaining: int = Field(..., ge=0, description="Remaining EMI months")
    hidden_apr: float = Field(..., gt=0, description="Annualized interest rate (e.g. 0.24 = 24%)")


class Transaction(BaseModel):
    """A single ledger entry in the player's history."""
    month: int = Field(..., ge=1, le=12)
    description: str
    amount: float = Field(..., description="Negative = deduction, positive = income")


class ScenarioOption(BaseModel):
    """One of the three choices presented to the player each month."""
    option_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique ID for this option",
    )
    text: str = Field(..., min_length=1, description="Player-facing description")
    type: OptionType = Field(..., description="Mechanical type of this option")
    base_cost: float = Field(..., ge=0, description="Base monetary cost (₹)")


class PostMortemReport(BaseModel):
    """The final educational report delivered when the game ends."""
    summary: str = Field(..., description="A brutal 3-sentence reality check or victory summary.")
    educational_tips: list[str] = Field(
        ...,
        min_length=1,
        max_length=3,
        description="Actionable financial advice tailored to the player's specific mistakes.",
    )


class Scenario(BaseModel):
    """
    An AI-generated financial emergency or temptation.
    Always contains exactly 3 options — one per OptionType.
    """
    scenario_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique scenario identifier",
    )
    title: str = Field(..., min_length=1)
    narrative: str = Field(..., min_length=1, description="Flavour text for the scenario")
    options: list[ScenarioOption] = Field(
        ...,
        min_length=3,
        max_length=3,
        description="Exactly 3 options (safe_drain, emi_trap, stress_spike)",
    )

    @field_validator("options")
    @classmethod
    def validate_option_types(cls, v: list[ScenarioOption]) -> list[ScenarioOption]:
        """Ensure exactly one option per OptionType."""
        types_present = {opt.type for opt in v}
        required = {OptionType.SAFE_DRAIN, OptionType.EMI_TRAP, OptionType.STRESS_SPIKE}
        if types_present != required:
            raise ValueError(
                f"Scenario must have exactly one option per type. "
                f"Got: {types_present}, need: {required}"
            )
        return v


# ---------------------------------------------------------------------------
# Top-Level Game State
# ---------------------------------------------------------------------------

class GameState(BaseModel):
    """
    The complete, self-contained game state.
    Passed from frontend → backend on every request and returned updated.
    """
    session_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="UUID identifying this play session",
    )
    month: int = Field(1, ge=1, le=12, description="Current virtual month (1–12)")
    game_over: bool = Field(False)
    win_status: Optional[bool] = Field(
        None,
        description="null while playing; True = survived 12 months, False = eliminated",
    )

    metrics: Metrics
    persona: Persona
    active_loans: list[Loan] = Field(default_factory=list)
    transaction_history: list[Transaction] = Field(default_factory=list)
    current_scenario: Optional[Scenario] = Field(
        None,
        description="The scenario the player must respond to this month",
    )
    post_mortem_report: Optional[PostMortemReport] = Field(
        None,
        description="AI-generated debrief — populated only when game_over is True",
    )


# ---------------------------------------------------------------------------
# API Request / Response Models
# ---------------------------------------------------------------------------

class ActionRequest(BaseModel):
    """Payload for POST /api/action."""
    current_state: GameState
    user_choice_id: str = Field(
        ...,
        min_length=1,
        description="The option_id the player chose from current_scenario.options",
    )
