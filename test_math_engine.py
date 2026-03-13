"""Quick smoke tests for math_engine.py"""
from app.models import *
from app.math_engine import *

# EMI sanity
emi = calculate_emi(10000, 0.24, 6)
print(f"EMI(10k) = {emi}")
assert emi > 0

# Build state
state = GameState(
    metrics=Metrics(cash=50000.0, stress=0, total_debt=0.0),
    persona=Persona(income=40000.0, fixed_rent=12000.0, weaknesses=["FOMO", "impulse-buying"]),
    month=1,
)

# safe_drain
opt = ScenarioOption(text="Hospital", type=OptionType.SAFE_DRAIN, base_cost=15000)
s = apply_choice(state, opt)
assert s.metrics.cash == 35000.0, f"Expected 35000, got {s.metrics.cash}"
print(f"safe_drain OK: cash={s.metrics.cash}")

# emi_trap
opt2 = ScenarioOption(text="Phone EMI", type=OptionType.EMI_TRAP, base_cost=20000)
s2 = apply_choice(state, opt2)
assert s2.metrics.cash == 50000.0
assert len(s2.active_loans) == 1
print(f"emi_trap OK: loans={len(s2.active_loans)}, debt={s2.metrics.total_debt}")

# stress_spike
opt3 = ScenarioOption(text="Ignore", type=OptionType.STRESS_SPIKE, base_cost=0)
s3 = apply_choice(state, opt3)
assert s3.metrics.stress == 25
print(f"stress_spike OK: stress={s3.metrics.stress}")

# monthly_tick
s4 = monthly_tick(s)
exp = 35000 + 40000 - 12000
assert s4.metrics.cash == exp, f"Expected {exp}, got {s4.metrics.cash}"
print(f"monthly_tick OK: cash={s4.metrics.cash}")

# penalty (no trigger)
s5 = apply_penalty(s4)
assert s5.metrics.cash == exp
print("penalty (no trigger) OK")

# penalty (trigger)
broke = s.model_copy(deep=True)
broke.metrics.cash = -500.0
s6 = apply_penalty(broke)
assert s6.metrics.cash == -2000.0
assert s6.metrics.stress == 15
print(f"penalty (trigger) OK: cash={s6.metrics.cash}, stress={s6.metrics.stress}")

# game-over: continue
s7 = check_game_over(s4)
assert not s7.game_over
print("game_over (continue) OK")

# game-over: loss
loss = s4.model_copy(deep=True)
loss.metrics.stress = 100
s8 = check_game_over(loss)
assert s8.game_over and s8.win_status == False
print("game_over (loss) OK")

# game-over: win
win = s4.model_copy(deep=True)
win.month = 12
s9 = check_game_over(win)
assert s9.game_over and s9.win_status == True
print("game_over (win) OK")

# full pipeline
full = process_turn(state, opt)
print(f"Full pipeline OK: cash={full.metrics.cash}, txns={len(full.transaction_history)}")

print("\n=== ALL TESTS PASSED ===")
