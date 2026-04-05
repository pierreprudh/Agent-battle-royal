import time
from .agent import make_agents
from .world import World
from .interactions import InteractionTracker
from .battle import Zone, check_survival_conditions


class Engine:
    TICK_RATE = 10
    DT = 1.0 / TICK_RATE
    DEATH_LINGER_S = 1.5

    def __init__(self, n_warriors=8, n_rangers=6, n_assassins=5, n_shamans=4, n_berserkers=5):
        self._counts = (n_warriors, n_rangers, n_assassins, n_shamans, n_berserkers)
        self.world = World()
        self.agents = make_agents(*self._counts, self.world.WIDTH, self.world.HEIGHT)
        self.tracker = InteractionTracker()
        self.zone = Zone()
        self.tick_count = 0
        self.paused = False
        self.speed = 1.0
        self.game_over = False
        self.winner = None
        self._kill_feed: list[dict] = []

    def step(self):
        if self.paused or self.game_over:
            return self.snapshot(), []

        dt = self.DT * self.speed

        for agent in self.agents:
            self.world.update_agent(agent, dt, self.agents, self.zone)

        self.world.tick_resources()

        new_interactions = self.tracker.tick(self.agents)

        for ev in self.tracker.kill_events:
            self._kill_feed.insert(0, ev)
        self._kill_feed = self._kill_feed[:10]

        self.zone.tick(self.agents)
        check_survival_conditions(self.agents, dt * self.speed)

        self.tick_count += 1

        # Assassin survival timer resets on confirmed kill
        kill_ids = {ev["killer"] for ev in self.tracker.kill_events}
        for agent in self.agents:
            if agent.id in kill_ids and agent.role == "assassin":
                agent.survival_timer = 0.0

        # Remove lingered dead agents
        now = time.time()
        self.agents = [
            a for a in self.agents
            if a.alive or (now - a.died_at) < self.DEATH_LINGER_S
        ]

        alive = [a for a in self.agents if a.alive]
        if not self.game_over and len(alive) <= 1:
            self.game_over = True
            self.winner = alive[0].to_dict() if alive else None

        return self.snapshot(), new_interactions

    def snapshot(self) -> dict:
        return {
            "tick":            self.tick_count,
            "agents":          [a.to_dict() for a in self.agents],
            "interactions":    self.tracker.snapshot(),
            "resources":       self.world.resources_for_snapshot(),
            "zone":            self.zone.to_dict(),
            "game_over":       self.game_over,
            "winner":          self.winner,
            "kill_feed":       self._kill_feed[:5],
            "alive_count":     sum(1 for a in self.agents if a.alive),
        }

    def set_speed(self, speed: float):
        self.speed = max(0.25, min(4.0, speed))

    def set_paused(self, paused: bool):
        self.paused = paused

    def resize(self, n_warriors=8, n_rangers=6, n_assassins=5, n_shamans=4, n_berserkers=5):
        self._counts = (n_warriors, n_rangers, n_assassins, n_shamans, n_berserkers)
        self.world = World()
        self.agents = make_agents(*self._counts, self.world.WIDTH, self.world.HEIGHT)
        self.tracker = InteractionTracker()
        self.zone = Zone()
        self.tick_count = 0
        self.game_over = False
        self.winner = None
        self._kill_feed = []
