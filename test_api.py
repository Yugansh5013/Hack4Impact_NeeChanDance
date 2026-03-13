"""Quick smoke test for the running API server."""
import urllib.request
import json

BASE = "http://127.0.0.1:8000"

# 1. Health check
r = urllib.request.urlopen(BASE + "/")
print("Health:", json.loads(r.read()))

# 2. Start game
req = urllib.request.Request(
    BASE + "/api/start",
    data=b"",
    method="POST",
    headers={"Content-Type": "application/json"},
)
r = urllib.request.urlopen(req)
state = json.loads(r.read())

print("\n--- /api/start ---")
print(f"session_id: {state['session_id'][:8]}...")
print(f"month:      {state['month']}")
print(f"cash:       {state['metrics']['cash']}")
print(f"stress:     {state['metrics']['stress']}")
print(f"income:     {state['persona']['income']}")
print(f"rent:       {state['persona']['fixed_rent']}")
print(f"weaknesses: {state['persona']['weaknesses']}")
print(f"scenario:   {state['current_scenario']['title']}")
print(f"options:    {len(state['current_scenario']['options'])}")
for o in state["current_scenario"]["options"]:
    print(f"  [{o['type']:12}] Rs.{o['base_cost']:>8.0f}  {o['text'][:60]}")

# 3. Take action (pick safe_drain)
safe_opt = [o for o in state["current_scenario"]["options"] if o["type"] == "safe_drain"][0]
action_payload = json.dumps({
    "current_state": state,
    "user_choice_id": safe_opt["option_id"],
}).encode()

req2 = urllib.request.Request(
    BASE + "/api/action",
    data=action_payload,
    method="POST",
    headers={"Content-Type": "application/json"},
)
r2 = urllib.request.urlopen(req2)
state2 = json.loads(r2.read())

print("\n--- /api/action (safe_drain) ---")
print(f"month:    {state2['month']}")
print(f"cash:     {state2['metrics']['cash']}")
print(f"stress:   {state2['metrics']['stress']}")
print(f"game_over:{state2['game_over']}")
print(f"scenario: {state2['current_scenario']['title']}")
print(f"txn count:{len(state2['transaction_history'])}")

print("\n=== ALL API SMOKE TESTS PASSED ===")
