import uuid
import time
import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .agent import Agent

INTERACTION_COLORS = {
    "COOPERATE":       "#22c55e",
    "COMPETE":         "#f97316",
    "NEGOTIATE":       "#3b82f6",
    "ATTACK":          "#ef4444",
    "FLEE":            "#a855f7",
    "SHARE_KNOWLEDGE": "#eab308",
    "HOARD":           "#6b7280",
    "FIGHT":           "#dc2626",
    "PATROL_TOGETHER": "#06b6d4",
    "AMBUSH":          "#4c1d95",
    "HEAL":            "#c4b5fd",
}

INTERACTION_DURATION = {
    "COOPERATE":       2000,
    "COMPETE":         1500,
    "NEGOTIATE":       2500,
    "ATTACK":          1000,
    "FLEE":            800,
    "SHARE_KNOWLEDGE": 3000,
    "HOARD":           1200,
    "FIGHT":           1800,
    "PATROL_TOGETHER": 2200,
    "AMBUSH":          600,
    "HEAL":            2500,
}

# (target_dmg, source_retaliation) — negative = heal
DAMAGE_MAP = {
    "ATTACK":          (0.32, 0.07),
    "FIGHT":           (0.26, 0.26),
    "COMPETE":         (0.12, 0.04),
    "FLEE":            (0.04, 0.00),
    "COOPERATE":       (0.00,  0.00),  # no healing in a battle royale
    "NEGOTIATE":       (0.00,  0.00),
    "SHARE_KNOWLEDGE": (0.00,  0.00),
    "HOARD":           (0.10,  0.00),
    "PATROL_TOGETHER": (0.00,  0.00),
    "AMBUSH":          (0.50,  0.00),
    "HEAL":            (-0.05, 0.00),  # shaman-only, costs nothing
}


@dataclass
class Interaction:
    id: str        = field(default_factory=lambda: str(uuid.uuid4())[:8])
    type: str      = "COOPERATE"
    source: str    = ""
    target: str    = ""
    created_at: float = field(default_factory=time.time)
    duration_ms: int  = 2000
    llm_pending: bool  = True
    llm_resolved: bool = False

    @property
    def age_ms(self) -> int:
        return int((time.time() - self.created_at) * 1000)

    @property
    def alive(self) -> bool:
        return self.age_ms < self.duration_ms

    def resolve_llm(self, itype: str):
        self.type = itype
        self.llm_pending = False
        self.llm_resolved = True
        self.duration_ms = INTERACTION_DURATION.get(itype, 2000) + random.randint(-200, 200)

    def to_dict(self):
        return {
            "id":          self.id,
            "type":        self.type,
            "source":      self.source,
            "target":      self.target,
            "age_ms":      self.age_ms,
            "duration_ms": self.duration_ms,
            "color":       INTERACTION_COLORS.get(self.type, "#ffffff"),
            "llm_pending": self.llm_pending,
        }


def resolve_interaction(a: "Agent", b: "Agent") -> str:
    """Rule-based interaction resolution for the new 5-role cast."""
    roles = tuple(sorted([a.role, b.role]))

    # --- Assassin logic (always aggressive) ---
    if "assassin" in roles:
        assassin = a if a.role == "assassin" else b
        other    = b if a.role == "assassin" else a
        if other.role == "assassin":
            return "FIGHT"
        # Assassin ambushes lone/weak targets; flees berserkers in rage
        if other.role == "berserker" and other.is_raging:
            return "FLEE"
        return "AMBUSH"

    # --- Berserker logic ---
    if "berserker" in roles:
        berserk = a if a.role == "berserker" else b
        other   = b if a.role == "berserker" else a
        if other.role == "berserker":
            return "FIGHT"
        if other.role == "shaman" and not berserk.is_raging:
            return "NEGOTIATE"
        return "ATTACK"

    # --- Warrior vs others ---
    if roles == ("ranger", "warrior"):
        return "FLEE"   # ranger always flees warrior
    if roles == ("shaman", "warrior"):
        # Territorial warrior might ignore wisdom
        return "NEGOTIATE" if a.personality.territorial < 0.6 or b.personality.territorial < 0.6 else "ATTACK"
    if roles == ("warrior", "warrior"):
        return "FIGHT"

    # --- Ranger vs others ---
    if roles == ("ranger", "shaman"):
        return "HEAL" if random.random() < 0.5 else "COOPERATE"
    if roles == ("ranger", "ranger"):
        return "COOPERATE" if (a.personality.curious + b.personality.curious) / 2 > 0.4 else "COMPETE"

    # --- Shaman vs others ---
    if roles == ("shaman", "shaman"):
        return "SHARE_KNOWLEDGE"

    return "NEGOTIATE"


def _kill(agent: "Agent", killer: "Agent", kill_events: list):
    import time as t
    agent.alive = False
    agent.state = "dead"
    agent.died_at = t.time()
    killer.kills += 1
    # Warrior bonus HP on kill
    if killer.role == "warrior":
        killer.health = min(killer.max_health, killer.health + 0.08)
    kill_events.append({
        "killer": killer.id, "killer_role": killer.role,
        "victim": agent.id,  "victim_role": agent.role,
    })


def apply_damage(source: "Agent", target: "Agent", itype: str, kill_events: list):
    base_tgt, base_src = DAMAGE_MAP.get(itype, (0.0, 0.0))

    # Berserker rage multiplies outgoing damage
    tgt_dmg = base_tgt * source.damage_multiplier if base_tgt > 0 else base_tgt
    src_ret = base_src * target.damage_multiplier if base_src > 0 else base_src

    # Target takes damage
    if tgt_dmg != 0:
        target.health = max(0.0, min(target.max_health, target.health - tgt_dmg))
        if tgt_dmg > 0 and target.health <= 0 and target.alive:
            _kill(target, source, kill_events)

    # Source takes retaliation
    if src_ret != 0:
        source.health = max(0.0, min(source.max_health, source.health - src_ret))
        if src_ret > 0 and source.health <= 0 and source.alive:
            _kill(source, target, kill_events)

    # Survival timer resets for aggressive interactions
    if itype in ("ATTACK", "FIGHT", "AMBUSH"):
        for ag in (source, target):
            if ag.role in ("warrior", "assassin", "berserker"):
                ag.survival_timer = 0.0

    # Shaman influence tracker
    if itype in ("HEAL", "SHARE_KNOWLEDGE", "COOPERATE"):
        if source.role == "shaman":
            source.influenced_ids.add(target.id)
        if target.role == "shaman":
            target.influenced_ids.add(source.id)


class InteractionTracker:
    COOLDOWN_S = 2.0
    ASSASSIN_COOLDOWN_S = 1.0  # assassins can strike more often

    def __init__(self):
        self._cooldowns: dict[tuple, float] = {}
        self.active: list[Interaction] = []
        self.kill_events: list[dict] = []

    def _cooldown_for(self, a: "Agent", b: "Agent") -> float:
        if a.role == "assassin" or b.role == "assassin":
            return self.ASSASSIN_COOLDOWN_S
        return self.COOLDOWN_S

    def tick(self, agents: list["Agent"]) -> list[Interaction]:
        now = time.time()
        self.kill_events.clear()
        self.active = [i for i in self.active if i.alive]

        new_interactions = []
        from .agent import PERCEPTION

        for i in range(len(agents)):
            for j in range(i + 1, len(agents)):
                a, b = agents[i], agents[j]
                if not a.alive or not b.alive:
                    continue

                radius = max(PERCEPTION[a.role], PERCEPTION[b.role])
                dist = ((a.x - b.x) ** 2 + (a.y - b.y) ** 2) ** 0.5
                if dist > radius:
                    continue

                pair = (min(a.id, b.id), max(a.id, b.id))
                cooldown = self._cooldown_for(a, b)
                if now - self._cooldowns.get(pair, 0) < cooldown:
                    continue
                self._cooldowns[pair] = now

                itype = resolve_interaction(a, b)
                interaction = Interaction(
                    type=itype,
                    source=a.id,
                    target=b.id,
                    duration_ms=INTERACTION_DURATION[itype] + random.randint(-200, 200),
                )
                self.active.append(interaction)
                new_interactions.append(interaction)

                apply_damage(a, b, itype, self.kill_events)

                a.add_memory({"with": b.id, "type": itype, "role": b.role})
                b.add_memory({"with": a.id, "type": itype, "role": a.role})

                if itype in ("FLEE",):
                    a.state = "fleeing" if a.personality.cautious > 0.4 else "interacting"
                    b.state = "interacting"
                elif itype in ("AMBUSH",):
                    a.state = "interacting"
                    b.state = "fleeing"
                else:
                    a.state = "interacting"
                    b.state = "interacting"

        return new_interactions

    def snapshot(self) -> list[dict]:
        return [i.to_dict() for i in self.active if i.alive]
