import React from "react";

const ROLE_COLOR = {
  warrior: "#ef4444", ranger: "#22c55e", assassin: "#7c3aed",
  shaman: "#f59e0b", berserker: "#f97316",
};
const ROLE_EMOJI = {
  warrior: "⚔️", ranger: "🏹", assassin: "🥷", shaman: "🔮", berserker: "💢",
};
const STATE_COLOR = {
  moving: "#6b7280", interacting: "#ffffff", fleeing: "#f0abfc",
  raging: "#fbbf24", idle: "#374151", dead: "#1f2937",
};
const INTERACTION_COLOR = {
  COOPERATE: "#22c55e", COMPETE: "#f97316", NEGOTIATE: "#3b82f6",
  ATTACK: "#ef4444", FLEE: "#a855f7", SHARE_KNOWLEDGE: "#eab308",
  HOARD: "#6b7280", FIGHT: "#dc2626", PATROL_TOGETHER: "#06b6d4",
  AMBUSH: "#4c1d95", HEAL: "#c4b5fd",
};

function PersonalityBar({ label, value, color }) {
  return (
    <div className="flex items-center gap-2 text-xs mb-1">
      <span className="w-20 text-gray-400">{label}</span>
      <div className="flex-1 bg-gray-800 rounded-full h-1.5">
        <div className="h-1.5 rounded-full" style={{ width: `${value * 100}%`, background: color }} />
      </div>
      <span className="w-8 text-right text-gray-300">{(value * 100).toFixed(0)}%</span>
    </div>
  );
}

function HealthBar({ health, maxHealth }) {
  const pct = Math.max(0, health / maxHealth);
  const color = pct > 0.6 ? "#22c55e" : pct > 0.3 ? "#eab308" : "#ef4444";
  return (
    <div>
      <div className="flex justify-between text-xs text-gray-400 mb-1">
        <span>HP</span>
        <span style={{ color }}>{(pct * 100).toFixed(0)}%</span>
      </div>
      <div className="bg-gray-800 rounded-full h-2">
        <div className="h-2 rounded-full transition-all" style={{ width: `${pct * 100}%`, background: color }} />
      </div>
    </div>
  );
}

export default function Inspector({ agent, onClose }) {
  if (!agent) return null;

  const hpPct = agent.max_health ? agent.health / agent.max_health : agent.health;

  return (
    <div className="w-64 bg-gray-900 border border-gray-700 rounded-xl p-4 shadow-2xl">

      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <span className="text-lg">{ROLE_EMOJI[agent.role]}</span>
          <div>
            <span className="font-bold text-sm" style={{ color: ROLE_COLOR[agent.role] }}>
              {agent.role.charAt(0).toUpperCase() + agent.role.slice(1)}
            </span>
            <span className="text-gray-500 text-xs font-mono ml-2">#{agent.id}</span>
          </div>
        </div>
        <button onClick={onClose} className="text-gray-500 hover:text-white text-lg leading-none">×</button>
      </div>

      {/* Health */}
      <div className="mb-4">
        <HealthBar health={agent.health} maxHealth={agent.max_health || 1} />
      </div>

      {/* Status row */}
      <div className="flex items-center gap-3 mb-4 text-xs">
        <div className="flex items-center gap-1">
          <span className="text-gray-500">State</span>
          <span className="font-medium" style={{ color: STATE_COLOR[agent.state] || "#fff" }}>
            {agent.state}
          </span>
        </div>
        <div className="flex items-center gap-1 ml-auto">
          <span className="text-gray-500">Kills</span>
          <span className="font-bold text-white">{agent.kills}</span>
          {agent.kills > 0 && <span className="text-red-400">💀</span>}
        </div>
      </div>

      {/* Personality */}
      <div className="mb-4">
        <div className="text-xs text-gray-500 uppercase tracking-wider mb-2">Personality</div>
        <PersonalityBar label="Cautious"    value={agent.personality.cautious}    color="#3b82f6" />
        <PersonalityBar label="Territorial" value={agent.personality.territorial} color="#ef4444" />
        <PersonalityBar label="Curious"     value={agent.personality.curious}     color="#22c55e" />
      </div>

      {/* Memory */}
      <div>
        <div className="text-xs text-gray-500 uppercase tracking-wider mb-2">Memory</div>
        {agent.memory.length === 0 ? (
          <div className="text-xs text-gray-600 italic">No interactions yet</div>
        ) : (
          <div className="space-y-1.5">
            {[...agent.memory].reverse().map((m, i) => (
              <div key={i} className="flex items-center gap-2 text-xs">
                <span
                  className="px-1.5 py-0.5 rounded text-xs font-semibold flex-shrink-0"
                  style={{
                    background: INTERACTION_COLOR[m.type] || "#888",
                    color: m.type === "AMBUSH" || m.type === "HEAL" ? "#fff" : "#000",
                  }}
                >
                  {m.type.toLowerCase().replace(/_/g, " ")}
                </span>
                {m.llm && <span title="LLM decided" className="text-purple-400 flex-shrink-0">🤖</span>}
                <span className="text-gray-400 truncate">
                  {ROLE_EMOJI[m.role]} <span className="font-mono text-gray-600">#{m.with?.slice(0, 4)}</span>
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
