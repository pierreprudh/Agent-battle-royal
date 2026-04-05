import math
import time


class Zone:
    CX = 400
    CY = 300
    INITIAL_RADIUS = 450.0
    MIN_RADIUS = 40.0
    SHRINK_PER_TICK = 10.0
    SHRINK_EVERY = 20          # ticks (~2s at 10Hz)
    OUTSIDE_DAMAGE = 0.018     # HP per tick outside — immediately painful
    OUTSIDE_DAMAGE_RAMP = 1.06 # escalates fast the longer they stay outside

    def __init__(self):
        self.radius = self.INITIAL_RADIUS
        self._tick = 0
        self._outside_ticks: dict[str, int] = {}  # agent_id → consecutive ticks outside

    def tick(self, agents: list):
        self._tick += 1
        if self._tick % self.SHRINK_EVERY == 0:
            self.radius = max(self.MIN_RADIUS, self.radius - self.SHRINK_PER_TICK)

        at_minimum = self.radius <= self.MIN_RADIUS
        surge_dmg = 0.015 if at_minimum else 0.0  # everyone takes damage when zone is fully closed

        for agent in agents:
            if not agent.alive:
                continue
            dist = math.sqrt((agent.x - self.CX) ** 2 + (agent.y - self.CY) ** 2)
            if dist > self.radius:
                ticks_out = self._outside_ticks.get(agent.id, 0) + 1
                self._outside_ticks[agent.id] = ticks_out
                dmg = self.OUTSIDE_DAMAGE * (self.OUTSIDE_DAMAGE_RAMP ** min(ticks_out, 30))
                agent.health = max(0.0, agent.health - dmg)
            else:
                self._outside_ticks.pop(agent.id, None)
                if surge_dmg:
                    agent.health = max(0.0, agent.health - surge_dmg)

            if agent.health <= 0 and agent.alive:
                agent.alive = False
                agent.state = "dead"
                agent.died_at = time.time()

    def to_dict(self):
        return {"cx": self.CX, "cy": self.CY, "radius": round(self.radius, 1)}


def check_survival_conditions(agents: list, dt: float):
    """
    No passive HP drain by timer — agents only die from combat or zone.
    Berserker gets slow regen when calm.
    """
    for agent in agents:
        if not agent.alive:
            continue
        if agent.role == "berserker" and not agent.is_raging:
            agent.health = min(agent.max_health, agent.health + 0.0008)
