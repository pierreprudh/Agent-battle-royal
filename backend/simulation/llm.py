import aiohttp

MODEL = "qwen3.5:2b"
OLLAMA_URL = "http://localhost:11434/api/generate"

VALID_TYPES = {
    "COOPERATE", "COMPETE", "NEGOTIATE", "ATTACK", "FLEE",
    "SHARE_KNOWLEDGE", "HOARD", "FIGHT", "PATROL_TOGETHER",
    "AMBUSH", "HEAL",
}

_PROMPT = """\
Battle royale simulation. ONE word answer only, no explanation.

Agent A: {role_a} | hp={hp_a:.0%}{warn_a}
  cautious={cautious_a:.0%}  territorial={territorial_a:.0%}  curious={curious_a:.0%}

Agent B: {role_b} | hp={hp_b:.0%}{warn_b}
  cautious={cautious_b:.0%}  territorial={territorial_b:.0%}  curious={curious_b:.0%}

Zone is shrinking. They meet. Choose one:
COOPERATE | COMPETE | NEGOTIATE | ATTACK | FLEE | SHARE_KNOWLEDGE | HOARD | FIGHT | PATROL_TOGETHER | AMBUSH | HEAL

Answer:"""


async def query_ollama(agent_a, agent_b) -> str | None:
    warn_a = " ⚠ LOW" if agent_a.health < 0.3 else (" 🔥 RAGE" if agent_a.is_raging else "")
    warn_b = " ⚠ LOW" if agent_b.health < 0.3 else (" 🔥 RAGE" if agent_b.is_raging else "")

    prompt = _PROMPT.format(
        role_a=agent_a.role, hp_a=agent_a.health / agent_a.max_health, warn_a=warn_a,
        cautious_a=agent_a.personality.cautious,
        territorial_a=agent_a.personality.territorial,
        curious_a=agent_a.personality.curious,
        role_b=agent_b.role, hp_b=agent_b.health / agent_b.max_health, warn_b=warn_b,
        cautious_b=agent_b.personality.cautious,
        territorial_b=agent_b.personality.territorial,
        curious_b=agent_b.personality.curious,
    )
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                OLLAMA_URL,
                json={
                    "model": MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.6, "num_predict": 12, "num_ctx": 256},
                },
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                raw = data.get("response", "").strip().upper()
                for word in raw.replace(",", " ").replace("\n", " ").split():
                    clean = word.strip(".:!?")
                    if clean in VALID_TYPES:
                        return clean
    except Exception:
        pass
    return None
