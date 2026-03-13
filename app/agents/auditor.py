"""
Chakravyuh — The Auditor Agent (The Judge)
============================================
Activated only when the game ends (win or loss).  Reviews the
player's entire transaction history and active loans to deliver
a structured ``PostMortemReport`` containing a narrative summary
and actionable educational tips.

Uses LangChain ``with_structured_output`` to guarantee the
response matches the ``PostMortemReport`` Pydantic schema.
"""

from __future__ import annotations

from langchain_core.messages import SystemMessage, HumanMessage

from app.models import GameState, PostMortemReport
from app.agents.llm_provider import get_llm


# ---------------------------------------------------------------------------
# System Prompts
# ---------------------------------------------------------------------------

AUDITOR_LOSS_PROMPT = """\
You are a forensic financial auditor. Your client has just suffered a complete
mental breakdown (Stress Level: {stress}) in Month {month}. They started with a
healthy income of ₹{income}/month, but they are now ruined.

Review their active loans: {active_loans}
Review their transaction history: {transaction_history}
Review their current cash: ₹{cash}

You must generate a PostMortemReport containing:
1. `summary`: A brutal, 3-sentence reality check explaining how they ruined
   themselves. Do not be polite. Point out the specific BNPL traps they fell for
   and how the debt spiral broke them.
2. `educational_tips`: Provide 2-3 specific, actionable financial tips based
   on the exact mistakes they made in their transaction history.

Output strictly in JSON matching the defined Pydantic schema.\
"""

AUDITOR_WIN_PROMPT = """\
You are a financial advisor. The client survived 12 months in a highly
predatory economy. Their final cash is ₹{cash} and final debt
is ₹{total_debt}. Their stress level ended at {stress}/100.

Review their transaction history: {transaction_history}
Review their active loans: {active_loans}

You must generate a PostMortemReport containing:
1. `summary`: A 3-sentence summary. Acknowledge their survival, but note the
   sacrifices they made. Warn them about lingering high stress or active debt.
2. `educational_tips`: Provide 2-3 specific, actionable financial tips to help
   them thrive (not just survive) next year, based on their playstyle.

Output strictly in JSON matching the defined Pydantic schema.\
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_transactions(state: GameState) -> str:
    """Produce a compact text summary of the transaction history."""
    if not state.transaction_history:
        return "No transactions."
    lines = []
    for tx in state.transaction_history:
        sign = "+" if tx.amount >= 0 else ""
        lines.append(f"  Month {tx.month}: {tx.description} ({sign}₹{tx.amount})")
    return "\n".join(lines)


def _format_loans(state: GameState) -> str:
    """Produce a compact text summary of active loans."""
    if not state.active_loans:
        return "None"
    return ", ".join(
        f"₹{loan.principal} @ {loan.hidden_apr*100:.0f}% APR "
        f"({loan.months_remaining} months left, EMI ₹{loan.emi})"
        for loan in state.active_loans
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_report(state: GameState) -> PostMortemReport:
    """
    Call the Auditor LLM to produce a ``PostMortemReport``.

    Parameters
    ----------
    state : GameState
        Final game state (must have ``game_over == True``).

    Returns
    -------
    PostMortemReport
        Validated Pydantic report with summary + educational_tips.
    """
    llm = get_llm(temperature=0.6)
    structured_llm = llm.with_structured_output(PostMortemReport)

    # Select prompt based on win/loss
    template = AUDITOR_WIN_PROMPT if state.win_status else AUDITOR_LOSS_PROMPT

    system_msg = template.format(
        month=state.month,
        cash=state.metrics.cash,
        total_debt=state.metrics.total_debt,
        stress=state.metrics.stress,
        income=state.persona.income,
        active_loans=_format_loans(state),
        transaction_history=_format_transactions(state),
    )

    human_msg = (
        f"The game is over. Win status: {'SURVIVED' if state.win_status else 'ELIMINATED'}. "
        f"Write the post-mortem report now."
    )

    report: PostMortemReport = structured_llm.invoke([
        SystemMessage(content=system_msg),
        HumanMessage(content=human_msg),
    ])

    return report
