# TODO

---

## ✅ Done

- [x] Python simulation engine (world, agents, interactions, engine)
- [x] LLM interaction layer — Ollama qwen3.5:2b, async per-interaction, non-blocking
- [x] FastAPI + WebSocket streaming at 10Hz
- [x] React + D3 visualization: nodes, health bars, zone ring, edge pulses, kill feed
- [x] Battle royale: shrinking zone, combat damage, storm surge, win detection, winner overlay
- [x] 5 distinct roles: Warrior ⚔️ Ranger 🏹 Assassin 🥷 Shaman 🔮 Berserker 💢
- [x] AMBUSH + HEAL interaction types
- [x] Berserker rage (speed + damage scale with missing HP)
- [x] Assassin stalks weakest isolated target
- [x] Shaman aura ring + gravitational pull
- [x] Force-model movement AI (zone-aware, threat-aware, role instincts)
- [x] Resources as healing pickups only — no passive HP drain
- [x] Tuned damage / HP / zone shrink for ~90s games

---

## 🔴 Next: LLM-Powered Movement

> **Current state:** the LLM only fires when two agents *meet* — it picks the interaction type
> (ATTACK, AMBUSH, HEAL…) and overrides the rule-based default. Movement between encounters
> is 100% deterministic: force vectors computed from zone distance, threat scores, and role
> instincts. The LLM has zero influence on *where* agents go.
>
> **Goal:** give each agent an LLM-decided **intent** that shapes its movement goal for the
> next few seconds. The physics engine still handles tick-by-tick forces — the LLM just sets
> the strategic objective.

---

### Why not call LLM every tick?

Movement runs at 10 Hz. A `qwen3.5:2b` call takes 1–3 s. Calling it per-tick would create a
3000-frame backlog instantly and completely decouple the model from the simulation.

The solution: **intent architecture**. The LLM returns a high-level goal that persists for
several seconds. The physics engine pursues that goal each tick without waiting for the model.

```
LLM call (every ~4s per agent, async)
  → returns intent label  e.g. "HUNT_RANGER"
    → stored on agent.movement_intent (expires after 4s)
      → _assign_waypoint() reads intent → sets target_x/y each waypoint refresh
        → force model steers toward target at 10Hz  ← no LLM involvement here
```

---

### Intent vocabulary

The LLM picks one of these labels. Each maps to a concrete waypoint strategy.

| Intent | Waypoint target | When LLM should pick it |
|---|---|---|
| `HUNT` | Nearest threatening enemy inside zone | Agent is healthy, sees weaker target |
| `FLEE` | Away from nearest threat + toward zone center | Agent is low HP or outmatched |
| `HEAL` | Nearest active resource inside zone | Agent HP < 50%, resource nearby |
| `HOLD` | Current position ± small jitter | Agent wants to set an ambush |
| `RALLY` | Nearest same-role ally | Agent wants backup before engaging |
| `RUSH_CENTER` | Zone center with small random offset | Agent is near zone edge, zone shrinking |

---

### Trigger conditions

An LLM movement query fires for an agent when **any** of these are true:

1. No intent set yet (first tick)
2. Current intent has expired (`now > agent.intent_expires_at`)
3. Agent HP drops by ≥ 20% since last decision (took heavy damage)
4. Zone radius shrinks below a new 50px threshold since last decision
5. A new enemy enters perception range (wasn't there last tick)
6. Agent makes a kill (situation changed — reassess)

Conditions 3–6 can interrupt a live intent early (urgent reassessment).

---

### Prompt design

Compact, structured, fits in 256 tokens (fast on 2B model).

```
Battle royale. ONE word answer only.

You are: assassin | HP=38% ⚠ LOW | kills=1 | inside zone (safe, edge 45px away)
Zone: r=180 shrinking fast

Visible agents (160px radius):
  warrior  HP=72%  dist=95  [threat HIGH]
  ranger   HP=28%  dist=130 [threat LOW — wounded]

Last 3 interactions: AMBUSH ranger, NEGOTIATE warrior, FLEE warrior

Personality: cautious=8% territorial=85% curious=7%

What is your movement goal?
HUNT | FLEE | HEAL | HOLD | RALLY | RUSH_CENTER

Answer:
```

Notes:
- `⚠ LOW` and zone urgency flags are added in Python before sending
- Visible agents are sorted by threat score descending (most dangerous first)
- Personality vector is always included — same agent with different personality should make different choices
- Memory (last 3 interactions) gives narrative continuity across decisions

---

### New files

**`backend/simulation/llm_movement.py`**
```python
async def query_movement_intent(agent, visible_agents, zone) -> str | None:
    # Build prompt, call Ollama, parse response
    # Returns one of the VALID_INTENTS or None (fallback to rule-based)
```

---

### Modified files

**`backend/simulation/agent.py`**

New fields on `Agent`:
```python
movement_intent: str | None = None        # current LLM-decided goal
intent_expires_at: float = 0.0            # timestamp when intent expires
intent_set_at: float = 0.0               # for "how long on this intent" display
last_hp_at_decision: float = 1.0         # for delta-HP trigger
last_zone_r_at_decision: float = 450.0   # for zone-shrink trigger
last_visible_ids: set = field(default_factory=set)  # for new-enemy trigger
```

`to_dict()` adds `movement_intent` (shown in Inspector).

**`backend/simulation/world.py`** — `_assign_waypoint()`

Check `agent.movement_intent` before role-specific logic:
```python
def _assign_waypoint(agent, all_agents, world, zone):
    intent = agent.movement_intent
    if intent == "HUNT":
        target = _find_hunt_target(agent, all_agents, zone)
        if target: agent.target_x, agent.target_y = target.x, target.y; return
    elif intent == "FLEE":
        # Away from nearest threat, biased toward zone center
        ...
    elif intent == "HEAL":
        res = world.nearest_active_resource(agent.x, agent.y, inside_zone=zone)
        if res: agent.target_x, agent.target_y = res["x"], res["y"]; return
    elif intent == "HOLD":
        agent.target_x = agent.x + random.uniform(-20, 20)
        agent.target_y = agent.y + random.uniform(-20, 20); return
    elif intent == "RALLY":
        ally = _find_nearest_ally(agent, all_agents)
        if ally: agent.target_x, agent.target_y = ally.x, ally.y; return
    elif intent == "RUSH_CENTER":
        agent.target_x = zone.CX + random.uniform(-30, 30)
        agent.target_y = zone.CY + random.uniform(-30, 30); return
    # fallback: existing role-based logic
    _assign_waypoint_by_role(agent, all_agents, world, zone)
```

**`backend/main.py`** — new `movement_decision_loop()` task

```python
async def movement_decision_loop():
    """Separate loop from broadcast. Checks each agent for intent triggers,
    fires async LLM queries, updates agent.movement_intent when resolved."""
    while True:
        await asyncio.sleep(0.5)  # check twice per second
        if engine.game_over:
            continue
        now = time.time()
        agent_map = {a.id: a for a in engine.agents if a.alive}
        visible_map = _compute_visible(engine.agents)  # precompute once per loop

        for agent in engine.agents:
            if not agent.alive:
                continue
            if _should_query_movement(agent, now, engine.zone, visible_map[agent.id]):
                asyncio.create_task(
                    resolve_movement_intent(agent, visible_map[agent.id], engine.zone)
                )
```

```python
async def resolve_movement_intent(agent, visible_agents, zone):
    result = await query_movement_intent(agent, visible_agents, zone)
    if result and agent.alive:
        agent.movement_intent = result
        agent.intent_expires_at = time.time() + 4.0
        agent.intent_set_at = time.time()
        agent.last_hp_at_decision = agent.health
        agent.last_zone_r_at_decision = zone.radius
```

---

### Frontend changes

**`Inspector.jsx`** — show current intent with a label + age

```
MOVEMENT INTENT
  🎯 HUNT  (set 1.2s ago)
```

Color-coded: FLEE=purple, HUNT=red, HEAL=green, HOLD=gray, RALLY=blue, RUSH_CENTER=orange.

**`SwarmGraph.jsx`** — small intent icon above node (optional, toggleable)

---

### Risks & mitigations

| Risk | Mitigation |
|---|---|
| LLM too slow — intent expires before response | Intent expiry = 4s, query fires at ~3.5s remaining. Rule-based fallback always runs. |
| LLM returns wrong token | `VALID_INTENTS` set, unknown response → `None` → fallback |
| Too many concurrent LLM calls (28 agents) | `movement_decision_loop` uses a semaphore: max 4 concurrent movement queries |
| Intent becomes stale (agent situation changes dramatically) | HP delta + zone delta + new-enemy triggers force early reassessment |
| Adds latency to game start | First intent queries fire at tick 1 but game runs immediately at rule-based baseline |

---

### Concurrency budget

At 28 agents, each querying every ~4s:
- ~7 queries/second average
- With max 4 concurrent and ~1.5s average latency: sustained ~2.7 queries/second processed
- Backlog builds but drains quickly; rule-based covers the gap

At 10 agents (mid-game):
- ~2.5 queries/second — well within budget

---

## 🟡 Polish

### Inner monologue in Inspector
**Files:** `simulation/llm.py`, `simulation/interactions.py`, `frontend/Inspector.jsx`
- Capture full LLM raw response (not just the one-word answer) when resolving interactions
- Store as `monologue` on the Interaction object
- Inspector shows last monologue for selected agent with italic styling
- Example: *"A wounded ranger, isolated — easy prey. I ambush."*

### Scenario presets
**Files:** `frontend/Controls.jsx`, `frontend/App.jsx`, `backend/main.py`
- Dropdown to load preset rosters:
  - **Default** — 8 warriors / 6 rangers / 5 assassins / 4 shamans / 5 berserkers
  - **Deathmatch** — 10 assassins / 10 berserkers
  - **Shaman Cult** — 8 rangers / 10 shamans
  - **1v1** — 1 warrior vs 1 berserker

### Timeline scrubbing / replay
- Snapshot ring buffer (last 600 ticks ≈ 60s) stored in engine
- Frontend scrubber below the canvas to rewind and step through history
- Pause required to scrub; resume resumes from current tick

---

## 🔵 Future: DPO Continuous Learning

> **Goal:** use battle outcomes to fine-tune the LLM over time so agents
> genuinely improve at surviving — without any hand-coded reward shaping.
> The simulation becomes a self-contained data generator for preference training.

### Core idea

Every interaction the LLM decides produces a `(prompt, chosen, rejected)` triple
once the game ends:

- **Positive (chosen):** decisions made by the winner, or by agents that survived
  significantly longer than average
- **Negative (rejected):** the same prompt with the losing decision — either what
  actually happened to a dead agent, or the rule-based default the LLM overrode

```
Game ends
  → walk kill feed + survival times
    → for each LLM-decided interaction:
        if agent survived top 25%  → mark as "chosen"
        if agent died early        → mark as "rejected"
          → pair with same-context interaction from a survivor → DPO triple
```

---

### Data schema

Each training example stored as JSONL:

```json
{
  "prompt": "Battle royale simulation. ONE word answer only.\n\nAgent A: assassin | hp=38% ⚠ LOW\n  cautious=8% territorial=85% curious=7%\n\nAgent B: ranger | hp=72%\n  cautious=48% territorial=15% curious=37%\n\nZone is shrinking. They meet. Choose one:\nCOOPERATE | COMPETE | ... | AMBUSH | HEAL\n\nAnswer:",
  "chosen":   "AMBUSH",
  "rejected": "NEGOTIATE",
  "meta": {
    "game_id": "uuid",
    "tick": 312,
    "agent_id": "a1f3",
    "agent_role": "assassin",
    "agent_survived_ticks": 480,
    "game_total_ticks": 844,
    "survival_percentile": 0.91
  }
}
```

---

### Collection pipeline

**New file: `backend/simulation/dpo_logger.py`**

```python
class DPOLogger:
    def log_interaction(self, prompt, llm_response, agent_id, tick): ...
    def on_game_over(self, agents, winner, total_ticks): ...
        # scores each logged interaction by agent survival percentile
        # writes chosen/rejected pairs to dpo_data/game_{id}.jsonl
    def flush(self): ...
```

Hooked into:
- `main.py` → `resolve_with_llm()`: log every LLM decision + prompt at interaction time
- `engine.py` → game_over trigger: call `dpo_logger.on_game_over()`

**Output directory:** `dpo_data/` (gitignored, accumulates across games)

---

### Training

Once enough games are collected (suggest ~500 games / ~50k examples minimum):

```bash
# Install
pip install trl datasets transformers

# Fine-tune with DPO
python train_dpo.py \
  --model qwen3.5:2b \
  --data dpo_data/ \
  --output models/swarm-dpo-v1 \
  --epochs 3 \
  --beta 0.1        # DPO temperature — lower = closer to reference model
```

**New file: `train_dpo.py`** — uses HuggingFace `trl.DPOTrainer`:

```python
from trl import DPOTrainer, DPOConfig
from datasets import load_dataset
from transformers import AutoModelForCausalLM, AutoTokenizer

# Load and format JSONL data into HF dataset
# Run DPO training loop
# Save adapter (LoRA) or full fine-tune
# Export back to Ollama-compatible GGUF format
```

---

### Swapping the model back in

After training, the fine-tuned model replaces the base model in `llm.py`:

```python
MODEL = "swarm-dpo-v1"  # local Ollama model, converted from fine-tuned checkpoint
```

No other code changes — the prompt format stays identical.

---

### What to expect

Early games: LLM makes random-ish decisions (rule-based fills gaps).
After 100 games: model starts preferring aggressive assassin plays, cautious ranger retreats.
After 500+ games: role-appropriate strategies emerge without being explicitly programmed.
Interesting question: does the model generalise across roles, or overfit to the winner's role?

---

### Risks & open questions

| Question | Notes |
|---|---|
| Survivorship bias | Winners aren't always skilled — they may just be lucky (zone RNG). Mitigate by using survival percentile relative to role average, not absolute position. |
| Dataset imbalance | Warriors and berserkers die in combat more visibly; shamans die quietly to zone. Weight by interaction count per agent. |
| Prompt consistency | Prompts must be identical between training and inference — lock the template in a shared constant. |
| Model drift | After fine-tuning, model may become overconfident. Keep the rule-based fallback; add temperature back if needed. |
| GGUF conversion | HuggingFace → Ollama requires `llama.cpp` quantization step. Document this in a `TRAINING.md`. |
