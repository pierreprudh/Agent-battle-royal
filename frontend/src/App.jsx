import React, { useState, useCallback } from "react";
import { useSwarm } from "./hooks/useSwarm";
import SwarmGraph from "./components/SwarmGraph";
import Inspector from "./components/Inspector";
import Controls from "./components/Controls";

const ROLE_COLOR = {
  warrior: "#ef4444", ranger: "#22c55e",
  assassin: "#7c3aed", shaman: "#f59e0b", berserker: "#f97316",
};
const ROLE_EMOJI = {
  warrior: "⚔️", ranger: "🏹", assassin: "🥷", shaman: "🔮", berserker: "💢",
};

export default function App() {
  const { state, connected, setPaused, setSpeed, resize } = useSwarm();
  const [selectedAgent, setSelectedAgent] = useState(null);

  const liveAgent = selectedAgent
    ? (state.agents.find(a => a.id === selectedAgent.id) || null)
    : null;

  const handleSelectAgent = useCallback((agent) => {
    setSelectedAgent(prev => prev?.id === agent.id ? null : agent);
  }, []);

  return (
    <div className="flex h-screen bg-gray-950 overflow-hidden">
      {/* Left panel */}
      <div className="flex flex-col gap-3 p-4 flex-shrink-0 overflow-y-auto">
        <div className="flex items-center gap-2 mb-1">
          <div className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
          <span className="text-white font-bold tracking-wider text-sm">BATTLE ROYALE</span>
          <span className="text-gray-600 text-xs font-mono ml-1">{state.alive_count} alive</span>
        </div>

        <Controls
          connected={connected}
          tick={state.tick}
          agentCount={state.agents.length}
          aliveCount={state.alive_count}
          interactionCount={state.interactions.length}
          killFeed={state.kill_feed}
          onPause={setPaused}
          onSpeed={setSpeed}
          onResize={resize}
        />

        {liveAgent?.alive && (
          <Inspector agent={liveAgent} onClose={() => setSelectedAgent(null)} />
        )}
      </div>

      {/* Canvas */}
      <div className="flex-1 relative">
        <svg className="absolute inset-0 w-full h-full pointer-events-none opacity-5">
          <defs>
            <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
              <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#ffffff" strokeWidth="0.5" />
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#grid)" />
        </svg>

        <SwarmGraph
          agents={state.agents}
          interactions={state.interactions}
          resources={state.resources}
          zone={state.zone}
          onSelectAgent={handleSelectAgent}
        />

        <div className="absolute bottom-4 right-4 text-xs text-gray-700 font-mono">
          {state.interactions.length} active interactions
        </div>
      </div>

      {/* Winner overlay */}
      {state.game_over && (
        <div className="absolute inset-0 flex items-center justify-center bg-black/75 z-50">
          <div className="bg-gray-900 border border-gray-700 rounded-2xl p-10 text-center shadow-2xl max-w-sm w-full mx-4">
            <div className="text-5xl mb-3">🏆</div>
            <div className="text-gray-400 text-xs uppercase tracking-widest mb-3">Winner</div>
            {state.winner ? (
              <>
                <div className="text-4xl font-black mb-1" style={{ color: ROLE_COLOR[state.winner.role] }}>
                  {ROLE_EMOJI[state.winner.role]} {state.winner.role.charAt(0).toUpperCase() + state.winner.role.slice(1)}
                </div>
                <div className="font-mono text-gray-500 text-sm mb-5">#{state.winner.id}</div>
                <div className="flex justify-center gap-8 mb-6">
                  <div>
                    <div className="text-gray-500 text-xs">Kills</div>
                    <div className="text-white font-bold text-3xl">{state.winner.kills}</div>
                  </div>
                  <div>
                    <div className="text-gray-500 text-xs">HP left</div>
                    <div className="text-green-400 font-bold text-3xl">
                      {(state.winner.health / state.winner.max_health * 100).toFixed(0)}%
                    </div>
                  </div>
                </div>
              </>
            ) : (
              <div className="text-gray-400 text-lg mb-6">No survivors</div>
            )}
            <button
              onClick={() => resize({ warriors: 8, rangers: 6, assassins: 5, shamans: 4, berserkers: 5 })}
              className="w-full py-3 bg-red-900 hover:bg-red-700 rounded-xl text-white font-semibold transition-colors"
            >
              ↺ New Battle
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
