import asyncio
import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from simulation.engine import Engine
from simulation.llm import query_ollama

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("swarm")

engine = Engine()
clients: set[WebSocket] = set()


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(broadcast_loop())
    yield
    task.cancel()


app = FastAPI(lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


async def resolve_with_llm(interaction, agent_map: dict):
    src = agent_map.get(interaction.source)
    tgt = agent_map.get(interaction.target)
    if not src or not tgt:
        interaction.llm_pending = False
        return

    result = await query_ollama(src, tgt)

    if not interaction.alive:
        return

    if result:
        prev = interaction.type
        interaction.resolve_llm(result)
        for agent, other_id in [(src, tgt.id), (tgt, src.id)]:
            for m in reversed(agent.memory):
                if m.get("with") == other_id:
                    m["type"] = result
                    m["llm"] = True
                    break
        if prev != result:
            log.info(f"LLM override: {prev} → {result}  ({src.role} × {tgt.role})")
    else:
        interaction.llm_pending = False


async def broadcast_loop():
    while True:
        await asyncio.sleep(1 / Engine.TICK_RATE)

        snapshot, new_interactions = engine.step()

        # Only fire LLM tasks if game is still running
        if new_interactions and not engine.game_over:
            agent_map = {a.id: a for a in engine.agents}
            for interaction in new_interactions:
                asyncio.create_task(resolve_with_llm(interaction, agent_map))

        if not clients:
            continue

        msg = json.dumps(snapshot)
        dead = set()
        for ws in clients:
            try:
                await ws.send_text(msg)
            except Exception:
                dead.add(ws)
        clients.difference_update(dead)


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    clients.add(ws)
    try:
        while True:
            data = await ws.receive_text()
            cmd = json.loads(data)
            if cmd.get("action") == "pause":
                engine.set_paused(cmd.get("value", True))
            elif cmd.get("action") == "speed":
                engine.set_speed(cmd.get("value", 1.0))
            elif cmd.get("action") == "resize":
                engine.resize(
                    n_warriors=cmd.get("warriors", 8),
                    n_rangers=cmd.get("rangers", 6),
                    n_assassins=cmd.get("assassins", 5),
                    n_shamans=cmd.get("shamans", 4),
                    n_berserkers=cmd.get("berserkers", 5),
                )
    except WebSocketDisconnect:
        clients.discard(ws)


@app.get("/state")
def get_state():
    return engine.snapshot()
