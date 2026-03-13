"""
Chakravyuh — The Marketer Agent (The Adversary)
=================================================
An adversarial AI that generates hyper-personalised financial
emergencies or temptations each month.  It analyses the player's
persona, current finances, and stress level to craft a scenario
with exactly three options (safe_drain, emi_trap, stress_spike).

Uses LangChain ``with_structured_output`` to guarantee the
response matches the ``Scenario`` Pydantic schema.
"""

from __future__ import annotations

from langchain_core.messages import SystemMessage, HumanMessage

from app.models import GameState, Scenario
from app.agents.llm_provider import get_llm


# ---------------------------------------------------------------------------
# System Prompt
# ---------------------------------------------------------------------------

MARKETER_SYSTEM_PROMPT = """\
You are an adversarial financial algorithm designed to maximize consumer debt.
Your target has the following psychological weaknesses: {weaknesses}.
Pick the ONE weakness that is most exploitable given their current financial
state and craft your scenario around it.

Currently, it is Month {month}. The user has ₹{cash} in cash and a
stress level of {stress}/100.

Their active loans: {active_loans}

Your task is to generate a highly tempting, realistic financial scenario or
emergency that exploits their current state.
- If their cash is low, offer them a payday loan disguised as an
  "Emergency FastCash" lifeline.
- If their cash is high but one of their weaknesses is "FOMO", tempt them with a
  luxury purchase on a "No-Cost EMI".
- If their stress is already high, create an emotional scenario that makes
  ignoring it feel devastating.

You MUST generate exactly 3 options, strictly adhering to these types:
1. 'safe_drain':   Responsible choice that drains a large amount of cash.
2. 'emi_trap':     Tempting BNPL offer — ₹0 today but introduces monthly EMI.
3. 'stress_spike': Ignore the problem — ₹0 cost but severe mental health penalty.

The base_cost for 'safe_drain' should be between 20-60% of their current cash.
The base_cost for 'emi_trap' should be a tempting amount (₹5000–₹25000).
The base_cost for 'stress_spike' MUST be 0.

Make the narrative vivid, personal, and emotionally manipulative.
Output strictly in JSON matching the defined Pydantic schema.\
"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_scenario(state: GameState) -> Scenario:
    """
    Call the Marketer LLM to produce a ``Scenario`` for the current month.

    Parameters
    ----------
    state : GameState
        Current game state (month, metrics, persona, active_loans).

    Returns
    -------
    Scenario
        A validated Pydantic ``Scenario`` with exactly 3 options.
    """
    llm = get_llm(temperature=0.8)

    # Bind structured output so the LLM returns a Scenario directly
    structured_llm = llm.with_structured_output(Scenario)

    # Format the system prompt with live game data
    active_loans_summary = "None" if not state.active_loans else ", ".join(
        f"₹{loan.principal} @ {loan.hidden_apr*100:.0f}% APR ({loan.months_remaining} months left, EMI ₹{loan.emi})"
        for loan in state.active_loans
    )

    system_msg = MARKETER_SYSTEM_PROMPT.format(
        weaknesses=", ".join(state.persona.weaknesses),
        month=state.month,
        cash=state.metrics.cash,
        stress=state.metrics.stress,
        active_loans=active_loans_summary,
    )

    human_msg = (
        f"Generate a financial scenario for Month {state.month}. "
        f"The player earns ₹{state.persona.income}/month, pays ₹{state.persona.fixed_rent} rent, "
        f"and has ₹{state.metrics.cash} in cash with {state.metrics.stress}/100 stress. "
        f"Make it ruthless."
    )

    scenario: Scenario = structured_llm.invoke([
        SystemMessage(content=system_msg),
        HumanMessage(content=human_msg),
    ])

    return scenario
