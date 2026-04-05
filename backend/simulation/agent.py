import uuid
import random
from dataclasses import dataclass, field
from typing import Literal

Role = Literal["warrior", "ranger", "assassin", "shaman", "berserker"]
State = Literal["idle", "moving", "interacting", "fleeing", "raging", "dead"]

BASE_HP    = {"warrior": 0.9, "ranger": 0.6, "assassin": 0.45, "shaman": 0.7, "berserker": 0.8}
BASE_SPEED = {"warrior": 1.5, "ranger": 2.2, "assassin": 2.0, "shaman": 0.7, "berserker": 1.0}
PERCEPTION = {"warrior": 55, "ranger": 80, "assassin": 60, "shaman": 70, "berserker": 50}

ROLE_COLOR = {
    "warrior":   "#ef4444",
    "ranger":    "#22c55e",
    "assassin":  "#7c3aed",
    "shaman":    "#f59e0b",
    "berserker": "#f97316",
}
ROLE_EMOJI = {
    "warrior": "⚔️", "ranger": "🏹",
    "assassin": "🥷", "shaman": "🔮", "berserker": "💢",
}


@dataclass
class Personality:
    cautious: float
    territorial: float
    curious: float

    @classmethod
    def random_for_role(cls, role: Role) -> "Personality":
        ranges = {
            "warrior":   dict(c=(0.0, 0.3), t=(0.5, 0.8), q=(0.1, 0.4)),
            "ranger":    dict(c=(0.3, 0.6), t=(0.1, 0.3), q=(0.3, 0.6)),
            "assassin":  dict(c=(0.0, 0.1), t=(0.7, 1.0), q=(0.0, 0.2)),
            "shaman":    dict(c=(0.2, 0.4), t=(0.1, 0.3), q=(0.5, 0.8)),
            "berserker": dict(c=(0.0, 0.2), t=(0.4, 0.7), q=(0.0, 0.3)),
        }
        r = ranges[role]
        c = random.uniform(*r["c"])
        t = random.uniform(*r["t"])
        q = random.uniform(*r["q"])
        total = c + t + q
        return cls(cautious=c / total, territorial=t / total, curious=q / total)

    def to_dict(self):
        return {
            "cautious":    round(self.cautious, 3),
            "territorial": round(self.territorial, 3),
            "curious":     round(self.curious, 3),
        }


@dataclass
class Agent:
    id: str          = field(default_factory=lambda: str(uuid.uuid4())[:8])
    role: Role       = "warrior"
    x: float        = 0.0
    y: float        = 0.0
    vx: float       = 0.0
    vy: float       = 0.0
    personality: Personality = field(default_factory=lambda: Personality(0.33, 0.33, 0.34))
    state: State    = "moving"
    energy: float   = 1.0
    memory: list    = field(default_factory=list)
    target_x: float = 0.0
    target_y: float = 0.0
    waypoint_timer: float = 0.0
    # Battle royale
    health: float        = 1.0
    kills: int           = 0
    alive: bool          = True
    survival_timer: float = 0.0
    died_at: float       = 0.0
    # Shaman influence tracker
    influenced_ids: set  = field(default_factory=set)

    MAX_MEMORY = 5

    @property
    def max_health(self) -> float:
        return BASE_HP[self.role]

    @property
    def speed(self) -> float:
        base = BASE_SPEED[self.role]
        if self.role == "berserker":
            missing = 1.0 - (self.health / self.max_health)
            return base + missing * 3.0   # up to 4.0 at 0 HP
        return base

    @property
    def damage_multiplier(self) -> float:
        if self.role == "berserker":
            missing = 1.0 - (self.health / self.max_health)
            return 1.0 + missing * 2.0   # up to 3x at 0 HP
        return 1.0

    @property
    def is_raging(self) -> bool:
        return self.role == "berserker" and self.health < self.max_health * 0.5

    def add_memory(self, entry: dict):
        self.memory.append(entry)
        if len(self.memory) > self.MAX_MEMORY:
            self.memory.pop(0)

    def to_dict(self):
        return {
            "id":          self.id,
            "role":        self.role,
            "x":           round(self.x, 1),
            "y":           round(self.y, 1),
            "state":       "raging" if self.is_raging else self.state,
            "energy":      round(self.energy, 2),
            "health":      round(self.health, 3),
            "max_health":  round(self.max_health, 3),
            "kills":       self.kills,
            "alive":       self.alive,
            "personality": self.personality.to_dict(),
            "memory":      self.memory[-3:],
        }


def make_agents(
    n_warriors=8, n_rangers=6, n_assassins=5, n_shamans=4, n_berserkers=5,
    world_w=800, world_h=600,
) -> list[Agent]:
    agents = []
    counts = [
        ("warrior",   n_warriors),
        ("ranger",    n_rangers),
        ("assassin",  n_assassins),
        ("shaman",    n_shamans),
        ("berserker", n_berserkers),
    ]
    for role, count in counts:
        for _ in range(count):
            a = Agent(
                role=role,
                x=random.uniform(60, world_w - 60),
                y=random.uniform(60, world_h - 60),
                personality=Personality.random_for_role(role),
                health=BASE_HP[role],
            )
            a.target_x = random.uniform(0, world_w)
            a.target_y = random.uniform(0, world_h)
            agents.append(a)
    return agents
