import React, { useState } from "react";

const ROLES = [
  { key: "warriors",   label: "Warriors",   color: "#ef4444", emoji: "⚔️",  survival: "Fight every 15s" },
  { key: "rangers",    label: "Rangers",    color: "#22c55e", emoji: "🏹",  survival: "Eat every 10s" },
  { key: "assassins",  label: "Assassins",  color: "#7c3aed", emoji: "🥷",  survival: "Kill every 18s" },
  { key: "shamans",    label: "Shamans",    color: "#f59e0b", emoji: "🔮",  survival: "Influence 3+ agents/25s" },
  { key: "berserkers", label: "Berserkers", color: "#f97316", emoji: "💢",  survival: "Rages when hurt" },
];

export default function Controls({ connected, tick, agentCount, aliveCount, interactionCount, killFeed, onPause, onSpeed, onResize }) {
  const [paused, setPaused] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [counts, setCounts] = useState({ warriors: 8, rangers: 6, assassins: 5, shamans: 4, berserkers: 5 });

  function togglePause() {
    const next = !paused;
    setPaused(next);
    onPause(next);
  }

  function handleSpeed(e) {
    const v = parseFloat(e.target.value);
    setSpeed(v);
    onSpeed(v);
  }

  function handleCount(key, val) {
    setCounts(prev => ({ ...prev, [key]: Math.max(0, Math.min(30, parseInt(val) || 0)) }));
  }

  function handleRestart() {
    onResize(counts);
  }

  return (
    <div className="bg-gray-900 border border-gray-700 rounded-xl p-4 space-y-4 w-64">
      {/* Connection + tick */}
      <div className="flex items-center gap-2 text-xs">
        <div className={`w-2 h-2 rounded-full ${connected ? "bg-green-400" : "bg-red-500"}`} />
        <span className="text-gray-400">{connected ? "live" : "reconnecting"}</span>
        <span className="ml-auto text-gray-600 font-mono">tick {tick}</span>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-2 text-xs">
        <div className="bg-gray-800 rounded-lg p-2">
          <div className="text-gray-500">Total</div>
          <div className="text-white font-bold text-lg">{agentCount}</div>
        </div>
        <div className="bg-gray-800 rounded-lg p-2">
          <div className="text-gray-500">Alive</div>
          <div className="text-green-400 font-bold text-lg">{aliveCount}</div>
        </div>
        <div className="bg-gray-800 rounded-lg p-2">
          <div className="text-gray-500">Events</div>
          <div className="text-yellow-400 font-bold text-lg">{interactionCount}</div>
        </div>
      </div>

      {/* Controls */}
      <div className="space-y-2">
        <button onClick={togglePause}
          className={`w-full py-2 rounded-lg text-sm font-semibold transition-colors ${paused ? "bg-green-600 hover:bg-green-500" : "bg-gray-700 hover:bg-gray-600"}`}>
          {paused ? "▶ Resume" : "⏸ Pause"}
        </button>
        <div>
          <div className="flex justify-between text-xs text-gray-400 mb-1"><span>Speed</span><span>{speed}×</span></div>
          <input type="range" min="0.25" max="4" step="0.25" value={speed}
            onChange={handleSpeed} className="w-full accent-blue-500" />
        </div>
      </div>

      {/* Agent counts */}
      <div>
        <div className="text-xs text-gray-500 uppercase tracking-wider mb-2">New Game Setup</div>
        {ROLES.map(({ key, label, color, emoji }) => (
          <div key={key} className="flex items-center gap-2 mb-1.5">
            <span className="text-sm">{emoji}</span>
            <span className="text-xs flex-1" style={{ color }}>{label}</span>
            <input type="number" min="0" max="30" value={counts[key]}
              onChange={e => handleCount(key, e.target.value)}
              className="w-10 bg-gray-800 border border-gray-700 rounded px-1 py-0.5 text-xs text-center text-white" />
          </div>
        ))}
        <button onClick={handleRestart}
          className="w-full mt-2 py-2 rounded-lg text-sm font-semibold bg-red-900 hover:bg-red-700 text-red-200 transition-colors">
          ↺ New Battle
        </button>
      </div>

      {/* Kill feed */}
      {killFeed?.length > 0 && (
        <div>
          <div className="text-xs text-gray-500 uppercase tracking-wider mb-2">Kill Feed</div>
          <div className="space-y-1">
            {killFeed.map((ev, i) => {
              const kr = ROLES.find(r => r.key === ev.killer_role + "s") || {};
              const vr = ROLES.find(r => r.key === ev.victim_role + "s") || {};
              return (
                <div key={i} className="text-xs flex items-center gap-1 flex-wrap">
                  <span>{kr.emoji}</span>
                  <span className="font-mono text-gray-500">#{ev.killer.slice(0, 4)}</span>
                  <span className="text-gray-600">→</span>
                  <span>{vr.emoji}</span>
                  <span className="font-mono text-gray-500">#{ev.victim.slice(0, 4)}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Survival rules legend */}
      <div>
        <div className="text-xs text-gray-500 uppercase tracking-wider mb-2">Survival Conditions</div>
        <div className="space-y-1">
          {ROLES.map(({ emoji, label, survival, color }) => (
            <div key={label} className="flex items-start gap-1.5 text-xs">
              <span className="flex-shrink-0">{emoji}</span>
              <span style={{ color }} className="flex-shrink-0">{label}:</span>
              <span className="text-gray-500">{survival}</span>
            </div>
          ))}
          <div className="flex items-start gap-1.5 text-xs mt-1">
            <span>🔴</span>
            <span className="text-red-400">Zone:</span>
            <span className="text-gray-500">damage outside ring</span>
          </div>
        </div>
      </div>
    </div>
  );
}
