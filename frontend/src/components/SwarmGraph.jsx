import React, { useEffect, useRef } from "react";
import * as d3 from "d3";

const ROLE_COLOR = {
  warrior:   "#ef4444",
  ranger:    "#22c55e",
  assassin:  "#7c3aed",
  shaman:    "#f59e0b",
  berserker: "#f97316",
};
const ROLE_RADIUS = {
  warrior: 9, ranger: 7, assassin: 6, shaman: 10, berserker: 8,
};

const INTERACTION_LABEL = {
  COOPERATE: "coop", COMPETE: "comp", NEGOTIATE: "neg",
  ATTACK: "atk", FLEE: "flee", SHARE_KNOWLEDGE: "share",
  HOARD: "hoard", FIGHT: "fight", PATROL_TOGETHER: "patrol",
  AMBUSH: "ambush", HEAL: "heal",
};

function healthColor(h) {
  if (h > 0.6) return d3.interpolateRgb("#22c55e", "#eab308")((1 - h) / 0.4);
  return d3.interpolateRgb("#eab308", "#ef4444")((0.6 - h) / 0.6);
}

export default function SwarmGraph({ agents, interactions, resources, zone, onSelectAgent }) {
  const svgRef = useRef(null);
  const initRef = useRef(false);

  useEffect(() => {
    if (!svgRef.current || agents.length === 0) return;
    const svg = d3.select(svgRef.current);

    if (!initRef.current) {
      initRef.current = true;
      svg.selectAll("*").remove();
      svg.append("g").attr("class", "zone");
      svg.append("g").attr("class", "resources");
      svg.append("g").attr("class", "edges");
      svg.append("g").attr("class", "pulses");
      svg.append("g").attr("class", "auras");    // shaman aura rings
      svg.append("g").attr("class", "nodes");
      svg.append("g").attr("class", "healthbars");
      svg.append("g").attr("class", "labels");
    }

    const W = svgRef.current.clientWidth;
    const H = svgRef.current.clientHeight;
    const scaleX = d3.scaleLinear().domain([0, 800]).range([0, W]);
    const scaleY = d3.scaleLinear().domain([0, 600]).range([0, H]);
    const scaleR = W / 800;

    // --- Zone ---
    if (zone) {
      let zc = svg.select(".zone").selectAll("circle").data([zone]);
      zc.enter().append("circle")
        .attr("fill", "rgba(239,68,68,0.04)")
        .attr("stroke", "#ef4444")
        .attr("stroke-dasharray", "6 4")
        .attr("stroke-width", 1.5)
        .merge(zc)
        .attr("cx", scaleX(zone.cx))
        .attr("cy", scaleY(zone.cy))
        .attr("r", zone.radius * scaleR);
    }

    // --- Resources ---
    const resDots = svg.select(".resources").selectAll("circle").data(resources, (_, i) => i);
    resDots.enter().append("circle").merge(resDots)
      .attr("cx", d => scaleX(d.x))
      .attr("cy", d => scaleY(d.y))
      .attr("r", 5)
      .attr("fill", d => d.depleted ? "#374151" : "#16a34a")
      .attr("opacity", d => d.depleted ? 0.15 : 0.45);
    resDots.exit().remove();

    // --- Shaman aura rings ---
    const shamans = agents.filter(a => a.alive && a.role === "shaman");
    const auras = svg.select(".auras").selectAll("circle").data(shamans, d => d.id);
    auras.enter().append("circle")
      .attr("fill", "none")
      .attr("stroke", "#f59e0b")
      .attr("stroke-dasharray", "3 5")
      .attr("stroke-width", 1)
      .attr("opacity", 0.25)
      .merge(auras)
      .attr("cx", d => scaleX(d.x))
      .attr("cy", d => scaleY(d.y))
      .attr("r", 130 * scaleR);
    auras.exit().remove();

    // --- Edges ---
    const agentMap = new Map(agents.map(a => [a.id, a]));
    const edgeData = interactions.filter(i => agentMap.has(i.source) && agentMap.has(i.target));

    const edges = svg.select(".edges").selectAll("line").data(edgeData, d => d.id);
    edges.enter().append("line").attr("stroke-width", 1.5).attr("opacity", 0)
      .merge(edges)
      .attr("x1", d => scaleX(agentMap.get(d.source).x))
      .attr("y1", d => scaleY(agentMap.get(d.source).y))
      .attr("x2", d => scaleX(agentMap.get(d.target).x))
      .attr("y2", d => scaleY(agentMap.get(d.target).y))
      .attr("stroke", d => d.color)
      .attr("stroke-dasharray", d => d.llm_pending ? "4 3" : "none")
      .attr("stroke-width", d => d.type === "AMBUSH" ? 2.5 : 1.5)
      .attr("opacity", d => Math.max(0.1, 1 - d.age_ms / d.duration_ms));
    edges.exit().remove();

    // --- Pulses ---
    const pulses = svg.select(".pulses").selectAll("circle").data(edgeData, d => d.id);
    pulses.enter().append("circle").attr("r", 3.5).merge(pulses)
      .each(function(d) {
        const src = agentMap.get(d.source);
        const tgt = agentMap.get(d.target);
        const t = (d.age_ms % 800) / 800;
        d3.select(this)
          .attr("cx", scaleX(src.x + (tgt.x - src.x) * t))
          .attr("cy", scaleY(src.y + (tgt.y - src.y) * t))
          .attr("r", d.type === "AMBUSH" ? 5 : 3.5)
          .attr("fill", d.color)
          .attr("opacity", Math.max(0, 1 - d.age_ms / d.duration_ms));
      });
    pulses.exit().remove();

    // --- Edge labels ---
    const labelData = edgeData.filter(d => d.age_ms < 600);
    const edgeLabels = svg.select(".labels").selectAll("text.edge-label").data(labelData, d => d.id);
    edgeLabels.enter().append("text").attr("class", "edge-label")
      .attr("font-size", "9px").attr("fill", "#fff").attr("opacity", 0.7).attr("text-anchor", "middle")
      .merge(edgeLabels).each(function(d) {
        const src = agentMap.get(d.source);
        const tgt = agentMap.get(d.target);
        d3.select(this)
          .attr("x", scaleX((src.x + tgt.x) / 2))
          .attr("y", scaleY((src.y + tgt.y) / 2) - 6)
          .text(d.llm_pending ? "?" : (INTERACTION_LABEL[d.type] || d.type.toLowerCase()));
      });
    edgeLabels.exit().remove();

    // --- Nodes ---
    const nodes = svg.select(".nodes").selectAll("circle").data(agents, d => d.id);
    nodes.enter().append("circle")
      .attr("cursor", "pointer")
      .on("click", (_, d) => { if (d.alive) onSelectAgent(d); })
      .merge(nodes)
      .attr("cx", d => scaleX(d.x))
      .attr("cy", d => scaleY(d.y))
      .attr("r", d => {
        if (!d.alive) return 0;
        const base = ROLE_RADIUS[d.role] ?? 7;
        // Berserker grows when raging
        const rage = d.state === "raging" ? 1 + (1 - d.health / d.max_health) * 0.6 : 1;
        return base * rage * (0.7 + (d.health / (d.max_health || 1)) * 0.3);
      })
      .attr("fill", d => d.alive ? ROLE_COLOR[d.role] ?? "#888" : "#1f2937")
      .attr("stroke", d => {
        if (!d.alive) return "transparent";
        if (d.state === "raging") return "#fbbf24";
        if (d.state === "interacting") return "#fff";
        if (d.state === "fleeing") return "#f0abfc";
        return "transparent";
      })
      .attr("stroke-width", d => d.state === "raging" ? 3 : 2)
      .attr("opacity", d => d.alive ? 0.92 : 0);
    nodes.exit().remove();

    // --- Health bars ---
    const BAR_W = 18, BAR_H = 3, BAR_OFF = 13;
    const aliveAgents = agents.filter(a => a.alive);

    const hbBg = svg.select(".healthbars").selectAll("rect.hb-bg").data(aliveAgents, d => d.id + "-bg");
    hbBg.enter().append("rect").attr("class", "hb-bg").attr("rx", 1)
      .attr("fill", "#374151").attr("height", BAR_H)
      .merge(hbBg)
      .attr("x", d => scaleX(d.x) - BAR_W / 2)
      .attr("y", d => scaleY(d.y) + BAR_OFF)
      .attr("width", BAR_W);
    hbBg.exit().remove();

    const hbFill = svg.select(".healthbars").selectAll("rect.hb-fill").data(aliveAgents, d => d.id + "-fill");
    hbFill.enter().append("rect").attr("class", "hb-fill").attr("rx", 1).attr("height", BAR_H)
      .merge(hbFill)
      .attr("x", d => scaleX(d.x) - BAR_W / 2)
      .attr("y", d => scaleY(d.y) + BAR_OFF)
      .attr("width", d => BAR_W * Math.max(0, d.health / (d.max_health || 1)))
      .attr("fill", d => healthColor(d.health / (d.max_health || 1)));
    hbFill.exit().remove();

  }, [agents, interactions, resources, zone, onSelectAgent]);

  return <svg ref={svgRef} className="w-full h-full" style={{ background: "transparent" }} />;
}
