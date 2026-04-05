import { useEffect, useRef, useState, useCallback } from "react";

const WS_URL = "ws://localhost:8000/ws";

const DEFAULT_STATE = {
  tick: 0, agents: [], interactions: [], resources: [],
  zone: { cx: 400, cy: 300, radius: 450 },
  game_over: false, winner: null, kill_feed: [], alive_count: 0,
};

export function useSwarm() {
  const [state, setState] = useState(DEFAULT_STATE);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef(null);

  useEffect(() => {
    let ws, alive = true;
    function connect() {
      ws = new WebSocket(WS_URL);
      wsRef.current = ws;
      ws.onopen  = () => { if (alive) setConnected(true); };
      ws.onclose = () => { if (alive) { setConnected(false); setTimeout(connect, 1500); } };
      ws.onmessage = (e) => { if (alive) setState(JSON.parse(e.data)); };
    }
    connect();
    return () => { alive = false; ws?.close(); };
  }, []);

  const send = useCallback((msg) => {
    if (wsRef.current?.readyState === WebSocket.OPEN)
      wsRef.current.send(JSON.stringify(msg));
  }, []);

  const setPaused = useCallback((v) => send({ action: "pause", value: v }), [send]);
  const setSpeed  = useCallback((v) => send({ action: "speed", value: v }), [send]);
  const resize    = useCallback((counts) => send({ action: "resize", ...counts }), [send]);

  return { state, connected, setPaused, setSpeed, resize };
}
