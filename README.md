# Agent Swarm — Battle Royale


Project goal is to become familiar with agent swarm and reinforcement learning + memory management ! 

---


A Fortnite-style battle royale where AI agents fight for survival in a shrinking arena.
One winner. Agents only take damage from combat or the zone — never from timers.
Movement is driven by survival instinct: stay in the zone, hunt the weak, flee the strong.

A local LLM (Ollama / `qwen3.5:2b`) decides the outcome of every encounter in real-time.
Watch emergent strategy unfold at 10 ticks per second.

---

## How it works

```
Python Simulation  ──10Hz──▶  FastAPI + WebSocket  ──JSON──▶  React + D3
     │                               │
     │ zone shrinks every 2s         │ async Ollama call per encounter
     │ force-model movement          │ rule-based fires instantly
     │ combat damage                 │ LLM overrides when ready
     ▼                               ▼
  engine.py                       main.py
```

Every tick the simulation:
1. Moves each agent using a **force model** (zone pull + threat assessment + role instincts)
2. Checks proximity — any two agents within perception range trigger an **interaction**
3. A rule-based resolver fires the interaction type instantly (no latency)
4. An **async Ollama call** runs in parallel; if it responds before the interaction expires, it overrides the rule-based type
5. Damage / healing is applied immediately on the rule-based result
6. The full world state is serialised to JSON and broadcast to all connected clients

---

## Architecture

```
backend/
  simulation/
    agent.py        — Agent dataclass: role, position, personality, health, kills, memory
    world.py        — 2D 800×600 space, force-model movement, resource pickups
    interactions.py — Proximity detection, rule-based + LLM resolution, damage
    battle.py       — Zone: shrink, outside damage (escalating), storm surge at min radius
    engine.py       — 10Hz tick loop, kill feed, win detection, snapshot serialisation
    llm.py          — Async Ollama client (qwen3.5:2b), interaction prompt + parser
  main.py           — FastAPI app, WebSocket broadcast loop, async LLM task dispatch

frontend/
  src/
    hooks/
      useSwarm.js         — WebSocket connection, reconnect logic, state management
    components/
      SwarmGraph.jsx      — D3 SVG canvas: nodes, health bars, zone ring, edge pulses
      Inspector.jsx       — Selected agent: HP bar, state, kills, personality, memory
      Controls.jsx        — Pause/speed, roster config, kill feed, survival legend
    App.jsx               — Layout, winner overlay, wires everything together
```

---

## Roles

| | Role | HP | Speed | Combat style | Survival instinct |
|---|---|---|---|---|---|
| ⚔️ | **Warrior** | 0.9 | 1.5 | Seeks fights; +0.08 HP on kill | Pursues weaker agents, flees only if heavily outmatched (threat > 1.6) |
| 🏹 | **Ranger** | 0.6 | 2.2 | Kites; routes to resources for healing | Cautious — flees at parity (threat > 1.0); never pursues |
| 🥷 | **Assassin** | 0.45 | 2.0 | AMBUSH deals 0.50 dmg; shorter cooldown; stalks isolated targets | Only flees raging berserkers (threat > 1.9) |
| 🔮 | **Shaman** | 0.7 | 0.7 | HEAL allies; HOARD drains enemies; gravitational pull on nearby agents | Very cautious (threat > 0.9); never pursues |
| 💢 | **Berserker** | 0.8 | 1.0→4.0 | Speed and damage scale inversely with HP; charges nearest agent when raging | Never flees; always pursues; slow regen when calm |

Each agent has a **personality vector** `[cautious, territorial, curious]` sampled randomly within role-appropriate ranges. Two warriors with different vectors make different decisions under the same conditions — the LLM sees those numbers.

---

## Movement AI

Movement is a **force model** — multiple weighted vectors summed each tick:

| Force | Magnitude | Notes |
|---|---|---|
| Waypoint | 0.6× speed | Long-range role goal; recalculated every 2–5s |
| Zone pull | 1.8× speed (near edge) / **3.5× speed (outside)** | Overrides everything when outside zone |
| Threat flee | 1.8× speed × proximity | Steers away from agents above flee threshold |
| Prey pursuit | 0.9× speed × proximity | Steers toward agents below pursue threshold |
| Berserker charge | 1.5× speed | Toward nearest alive when raging |
| Shaman gravity | 0.10× | Non-shaman agents pulled toward nearby shamans |
| Jitter | ±0.5 | Prevents perfect straight-line movement |

Waypoints are always assigned inside `zone.radius − 120px` — no role ever targets the zone edge or outside it.

Role-specific waypoint logic:
- **Ranger** → nearest active resource inside zone, then fallback to zone interior
- **Warrior** → random point inside zone, biased toward center
- **Assassin** → lowest-HP isolated target inside zone
- **Shaman** → slow drift toward zone center
- **Berserker** → random roam inside zone

---

## Interaction system

When two agents enter each other's perception range and their cooldown has expired:

| Step | What happens |
|---|---|
| 1 | Rule-based type resolved instantly from role pair + personality |
| 2 | Interaction edge appears on graph (dashed `?` = LLM pending) |
| 3 | Async Ollama call fires (non-blocking) |
| 4 | LLM response overrides type if valid and interaction still alive |
| 5 | Edge goes solid with final label and colour |

**Cooldowns:** 2s standard · 1s for assassins

**Perception radii:** warrior 55px · ranger 80px · assassin 60px · shaman 70px · berserker 50px

### Damage table

| Type | Target HP | Source HP | Notes |
|---|---|---|---|
| ATTACK | −0.32 | −0.07 | Standard combat |
| FIGHT | −0.26 | −0.26 | Mutual — both pay |
| AMBUSH | −0.50 | 0 | Assassin opener, no retaliation |
| COMPETE | −0.12 | −0.04 | Loser takes more |
| FLEE | −0.04 | 0 | Small exit damage |
| HOARD | −0.10 | 0 | Shaman drains enemy |
| HEAL | +0.05 | 0 | Shaman heals ally |
| COOPERATE / NEGOTIATE / PATROL_TOGETHER | 0 | 0 | — |

Berserker's **damage multiplier** scales with missing HP — at 0 HP it would deal 3× (never fires in practice since death stops it).

---

## Zone

- Starts at radius **450px** (covers the full 800×600 map)
- Shrinks **10px every 2 seconds**, minimum **40px**
- Outside damage: **0.018 HP/tick**, escalating ×1.06 each consecutive tick outside — staying out 10 ticks deals ~0.032/tick
- **Storm surge**: once zone reaches minimum, all agents inside take **0.015 HP/tick** — guarantees the game ends
- Agents start fleeing the edge when within **100px** of it

---

## LLM integration

**Model:** `qwen3.5:2b` via Ollama (local, free, swappable)

**Prompt per interaction:**
```
Battle royale simulation. ONE word answer only.

Agent A: assassin | hp=38% ⚠ LOW
  cautious=8%  territorial=85%  curious=7%

Agent B: ranger | hp=72%
  cautious=48%  territorial=15%  curious=37%

Zone is shrinking. They meet. Choose one:
COOPERATE | COMPETE | NEGOTIATE | ATTACK | FLEE | SHARE_KNOWLEDGE |
HOARD | FIGHT | PATROL_TOGETHER | AMBUSH | HEAL

Answer:
```

- **Non-blocking**: LLM call fires as an `asyncio.create_task`; simulation never waits
- **Fallback**: rule-based type stays if LLM times out, errors, or returns invalid token
- **Visual**: dashed edge + `?` label while pending; solid + type label once resolved
- **Memory**: `🤖` badge in Inspector marks interactions the LLM decided

---

## WebSocket protocol

Server broadcasts at **10Hz**:

```json
{
  "tick": 312,
  "agents": [{
    "id": "a1f3c2d4",
    "role": "warrior",
    "x": 412.3, "y": 287.1,
    "state": "raging",
    "health": 0.31, "max_health": 0.9,
    "kills": 2,
    "personality": { "cautious": 0.12, "territorial": 0.71, "curious": 0.17 },
    "memory": [{ "with": "b2c4", "type": "FIGHT", "role": "berserker", "llm": true }]
  }],
  "interactions": [{
    "id": "i7a2",
    "type": "AMBUSH",
    "source": "a1f3c2d4", "target": "c9d1e5f6",
    "age_ms": 120, "duration_ms": 600,
    "color": "#4c1d95",
    "llm_pending": false
  }],
  "resources": [{ "x": 210, "y": 145, "depleted": false }],
  "zone": { "cx": 400, "cy": 300, "radius": 280.0 },
  "game_over": false,
  "winner": null,
  "kill_feed": [{ "killer": "a1f3c2d4", "killer_role": "warrior", "victim": "b2c4e8a1", "victim_role": "berserker" }],
  "alive_count": 9
}
```

---

## Setup

### Prerequisites
- Python 3.12+
- Node 18+
- [Ollama](https://ollama.com) running locally

```bash
ollama pull qwen3.5:2b
```

### Backend
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --port 8000 --reload
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**

The simulation starts immediately. Ollama calls are optional — the game runs fine without it (rule-based only).

---

## Controls

| Control | Effect |
|---|---|
| Click agent node | Open Inspector — HP bar, state, kills, personality, memory with 🤖 LLM badge |
| ⏸ Pause / ▶ Resume | Freeze simulation state |
| Speed slider | 0.25× – 4× simulation speed |
| Role count inputs | Configure roster for the next game |
| ↺ New Battle | Reset everything, start fresh |

---

## Roadmap

- [x] Python simulation engine (world, agents, interactions, engine)
- [x] LLM interaction layer — Ollama qwen3.5:2b, async per-encounter, non-blocking
- [x] FastAPI + WebSocket streaming at 10Hz
- [x] React + D3 visualization — nodes, health bars, zone ring, edge pulses, kill feed
- [x] Battle royale — shrinking zone, storm surge, combat damage, kill feed, winner overlay
- [x] 5 distinct roles — Warrior ⚔️  Ranger 🏹  Assassin 🥷  Shaman 🔮  Berserker 💢
- [x] Force-model movement AI — zone-aware, threat-aware, role instincts
- [x] Resources as healing pickups, no passive HP drain
- [ ] **LLM-powered movement** — intent architecture (HUNT / FLEE / HEAL / HOLD / RALLY / RUSH_CENTER), async queries every ~4s per agent (see TODO)
- [ ] Inner monologue panel — LLM reasoning surfaced in Inspector
- [ ] Scenario presets — Deathmatch, Shaman Cult, 1v1
- [ ] Timeline scrubbing / replay (60s ring buffer)

---

## Inspiration

- [MiroFish](https://github.com/666ghj/MiroFish) — LLM agent social simulation
- [OASIS by CAMEL-AI](https://github.com/camel-ai/oasis) — large-scale social simulation
- Craig Reynolds' Boids — emergent flocking from simple rules
- Fortnite — shrinking zone, last-one-standing format
