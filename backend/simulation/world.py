import random
import math
import time
from .agent import PERCEPTION

# How dangerous each role is in combat (base, before HP scaling)
ROLE_STRENGTH = {
    "warrior":   1.3,
    "berserker": 1.2,   # further scaled by rage_multiplier at runtime
    "assassin":  1.1,
    "ranger":    0.8,
    "shaman":    0.7,
}

# Threat score above which an agent will flee
FLEE_THRESHOLD = {
    "warrior":   1.6,   # fights unless heavily outmatched
    "berserker": 99.0,  # never flees — charges everything
    "assassin":  1.9,   # only flees raging berserkers
    "ranger":    1.0,   # cautious, flees at parity
    "shaman":    0.9,   # very cautious
}

# Threat score below which an aggressive agent will pursue
PURSUE_THRESHOLD = {
    "warrior":   0.65,
    "berserker": 0.0,   # always pursues (handled by rage logic)
    "assassin":  0.75,
    "ranger":    99.0,  # never actively pursues
    "shaman":    99.0,  # never actively pursues
}

# How far to look for threats / prey
THREAT_RADIUS = 160.0


class World:
    WIDTH = 800
    HEIGHT = 600
    N_RESOURCES = 12
    RESOURCE_RADIUS = 38.0
    RESOURCE_RESPAWN_S = 12.0

    def __init__(self):
        self.resources = [
            {
                "x": random.uniform(80, self.WIDTH - 80),
                "y": random.uniform(80, self.HEIGHT - 80),
                "depleted": False,
                "respawn_at": 0.0,
            }
            for _ in range(self.N_RESOURCES)
        ]

    def nearest_active_resource(self, x, y, inside_zone=None):
        active = [r for r in self.resources if not r["depleted"]]
        if inside_zone:
            # Prefer resources inside the zone
            in_zone = [
                r for r in active
                if math.sqrt((r["x"] - inside_zone.CX) ** 2 + (r["y"] - inside_zone.CY) ** 2) < inside_zone.radius
            ]
            if in_zone:
                active = in_zone
        if not active:
            return None
        return min(active, key=lambda r: (r["x"] - x) ** 2 + (r["y"] - y) ** 2)

    def tick_resources(self):
        now = time.time()
        for r in self.resources:
            if r["depleted"] and now >= r["respawn_at"]:
                r["depleted"] = False

    def update_agent(self, agent, dt: float, all_agents: list, zone):
        if not agent.alive:
            return

        speed = agent.speed * dt * 60
        agent.waypoint_timer -= dt

        # --- Resource pickup (all roles, no survival penalty) ---
        for res in self.resources:
            if res["depleted"]:
                continue
            d = math.sqrt((res["x"] - agent.x) ** 2 + (res["y"] - agent.y) ** 2)
            if d < self.RESOURCE_RADIUS:
                res["depleted"] = True
                res["respawn_at"] = time.time() + self.RESOURCE_RESPAWN_S
                agent.health = min(agent.max_health, agent.health + 0.08)
                break

        # ----------------------------------------------------------------
        # Force model: accumulate direction vectors, then apply as velocity
        # ----------------------------------------------------------------
        fx, fy = 0.0, 0.0

        # --- F1: Waypoint force (long-range goal, low priority) ---
        if agent.waypoint_timer <= 0:
            agent.waypoint_timer = random.uniform(2.5, 5.0)
            _assign_waypoint(agent, all_agents, self, zone)

        wdx = agent.target_x - agent.x
        wdy = agent.target_y - agent.y
        wd = math.sqrt(wdx ** 2 + wdy ** 2) + 0.001
        fx += (wdx / wd) * speed * 0.6
        fy += (wdy / wd) * speed * 0.6

        # --- F2: Zone force (pull toward center when near/outside edge) ---
        dist_to_center = math.sqrt((agent.x - zone.CX) ** 2 + (agent.y - zone.CY) ** 2)
        if dist_to_center > 0.001:
            to_cx = (zone.CX - agent.x) / dist_to_center
            to_cy = (zone.CY - agent.y) / dist_to_center

            if dist_to_center > zone.radius:
                # Outside zone — strong override pull
                zone_mag = speed * 3.5
                fx = to_cx * zone_mag   # override other forces
                fy = to_cy * zone_mag
            elif dist_to_center > zone.radius - 100:
                # Near edge — proportional nudge starts earlier and stronger
                edge_closeness = (dist_to_center - (zone.radius - 100)) / 100  # 0→1
                zone_mag = speed * 1.8 * edge_closeness
                fx += to_cx * zone_mag
                fy += to_cy * zone_mag

        # --- F3: Threat assessment (only if not already overridden by zone) ---
        if dist_to_center <= zone.radius:
            threat_fx, threat_fy, new_state = _threat_forces(agent, all_agents, speed)
            fx += threat_fx
            fy += threat_fy
            if new_state and not agent.is_raging:
                agent.state = new_state

        # --- F4: Role-specific instincts ---
        # Berserker charges nearest agent when raging (overrides threat flee)
        if agent.is_raging:
            nearest = _nearest_alive(agent, all_agents)
            if nearest:
                ddx = nearest.x - agent.x
                ddy = nearest.y - agent.y
                dd = math.sqrt(ddx ** 2 + ddy ** 2) + 0.001
                # Only charge if target is inside zone (don't chase outside)
                t_in_zone = math.sqrt((nearest.x - zone.CX) ** 2 + (nearest.y - zone.CY) ** 2) < zone.radius
                if t_in_zone:
                    fx += (ddx / dd) * speed * 1.5
                    fy += (ddy / dd) * speed * 1.5
            agent.state = "raging"

        # Shaman gravitational pull on nearby non-shaman agents
        if agent.role != "shaman":
            for other in all_agents:
                if other.role == "shaman" and other.alive:
                    d = math.sqrt((other.x - agent.x) ** 2 + (other.y - agent.y) ** 2)
                    if 0 < d < 140:
                        pull = 0.10 * (1 - d / 140)
                        fx += (other.x - agent.x) / d * pull
                        fy += (other.y - agent.y) / d * pull

        # --- F5: Jitter ---
        fx += random.uniform(-0.5, 0.5)
        fy += random.uniform(-0.5, 0.5)

        # Apply velocity (no world wrapping — clamp to bounds so zone pushes work)
        agent.vx = fx
        agent.vy = fy
        agent.x = max(0.0, min(self.WIDTH,  agent.x + agent.vx))
        agent.y = max(0.0, min(self.HEIGHT, agent.y + agent.vy))

        # State decay
        if agent.state in ("interacting", "fleeing") and not agent.is_raging:
            if random.random() < 0.025:
                agent.state = "moving"

    def resources_for_snapshot(self):
        return [{"x": r["x"], "y": r["y"], "depleted": r["depleted"]} for r in self.resources]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _combat_power(agent) -> float:
    hp_ratio = agent.health / agent.max_health
    strength = ROLE_STRENGTH[agent.role]
    # Berserker's power increases as HP drops
    if agent.role == "berserker":
        strength *= agent.damage_multiplier
    return hp_ratio * strength


def _threat_forces(agent, all_agents: list, speed: float):
    """
    Scan visible agents. Return (fx, fy, new_state).
    - Flee from threats above threshold
    - Pursue prey below threshold (aggressive roles only)
    """
    my_power = _combat_power(agent)
    flee_threshold = FLEE_THRESHOLD[agent.role]
    pursue_threshold = PURSUE_THRESHOLD[agent.role]

    flee_fx, flee_fy = 0.0, 0.0
    pursue_fx, pursue_fy = 0.0, 0.0
    max_threat = 0.0
    best_prey_score = 99.0
    new_state = None

    for other in all_agents:
        if not other.alive or other.id == agent.id:
            continue
        dx = other.x - agent.x
        dy = other.y - agent.y
        d = math.sqrt(dx * dx + dy * dy)
        if d > THREAT_RADIUS or d < 0.001:
            continue

        their_power = _combat_power(other)
        threat_score = their_power / (my_power + 0.001)
        proximity_factor = 1.0 - (d / THREAT_RADIUS)  # stronger when closer

        if threat_score > flee_threshold:
            # Push away, proportional to threat excess and proximity
            mag = speed * 1.8 * proximity_factor * min(threat_score / flee_threshold, 2.0)
            flee_fx -= (dx / d) * mag
            flee_fy -= (dy / d) * mag
            max_threat = max(max_threat, threat_score)
            new_state = "fleeing"

        elif threat_score < pursue_threshold:
            # Pull toward prey (only for naturally aggressive roles)
            prey_score = threat_score + d / THREAT_RADIUS
            if prey_score < best_prey_score:
                best_prey_score = prey_score
                mag = speed * 0.9 * proximity_factor
                pursue_fx = (dx / d) * mag
                pursue_fy = (dy / d) * mag
                if agent.state != "fleeing":
                    new_state = "moving"

    # Fleeing overrides pursuing
    if max_threat > flee_threshold:
        return flee_fx, flee_fy, "fleeing"
    if best_prey_score < pursue_threshold:
        return pursue_fx, pursue_fy, new_state

    return 0.0, 0.0, None


def _assign_waypoint(agent, all_agents: list, world: World, zone):
    """Long-range goal assignment. Zone-aware: never point outside zone."""
    cx, cy = zone.CX, zone.CY
    safe_r = max(zone.radius - 120, 20)  # keep a wide margin from edge

    if agent.role == "ranger":
        # Head for nearest resource that's inside the zone
        res = world.nearest_active_resource(agent.x, agent.y, inside_zone=zone)
        if res:
            agent.target_x = res["x"]
            agent.target_y = res["y"]
            return

    elif agent.role == "warrior":
        # Patrol the interior aggressively — random point inside safe zone
        angle = random.uniform(0, 2 * math.pi)
        r = random.uniform(0, safe_r * 0.9)
        agent.target_x = cx + math.cos(angle) * r
        agent.target_y = cy + math.sin(angle) * r
        return

    elif agent.role == "assassin":
        # Stalk best prey target
        prey = _find_prey(agent, all_agents, zone)
        if prey:
            agent.target_x = prey.x
            agent.target_y = prey.y
            return

    elif agent.role == "shaman":
        # Drift toward zone center slowly
        offset_x = random.uniform(-100, 100)
        offset_y = random.uniform(-100, 100)
        agent.target_x = cx + offset_x
        agent.target_y = cy + offset_y
        return

    elif agent.role == "berserker":
        # Roam the zone looking for fights
        angle = random.uniform(0, 2 * math.pi)
        r = random.uniform(0, safe_r)
        agent.target_x = cx + math.cos(angle) * r
        agent.target_y = cy + math.sin(angle) * r
        return

    # Fallback: random point inside safe zone
    angle = random.uniform(0, 2 * math.pi)
    r = random.uniform(0, safe_r)
    agent.target_x = cx + math.cos(angle) * r
    agent.target_y = cy + math.sin(angle) * r


def _find_prey(assassin, all_agents: list, zone) -> "Agent | None":
    """Assassin targets the weakest isolated agent inside the zone."""
    candidates = [
        a for a in all_agents
        if a.alive and a.id != assassin.id
        and math.sqrt((a.x - zone.CX) ** 2 + (a.y - zone.CY) ** 2) < zone.radius
    ]
    if not candidates:
        return None

    def prey_score(a):
        nearby_allies = sum(
            1 for o in all_agents
            if o.alive and o.id != a.id
            and math.sqrt((o.x - a.x) ** 2 + (o.y - a.y) ** 2) < 90
        )
        return (a.health / a.max_health) + nearby_allies * 0.25

    return min(candidates, key=prey_score)


def _nearest_alive(agent, all_agents: list):
    others = [a for a in all_agents if a.alive and a.id != agent.id]
    if not others:
        return None
    return min(others, key=lambda a: (a.x - agent.x) ** 2 + (a.y - agent.y) ** 2)
