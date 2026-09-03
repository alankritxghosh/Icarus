"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { Candidate, Confirmed } from "./types";

/**
 * A real-data decision graph, Canvas 2D rather than EvidenceGraph.tsx's
 * Three.js: that component is built for ~2,600 precomputed, build-time
 * nodes (site/build/build_graph.py). A repository's decisions are single
 * digits to a few dozen, computed live and changing as someone actually
 * confirms one -- a lightweight client-side force layout is the right tool
 * here, not a WebGL pipeline sized for two orders of magnitude more data.
 *
 * Interaction model (pan/zoom/drag, click for detail, Accept/Reject/Other)
 * ported from the standalone mockup this replaces, refined there across
 * several rounds: drag empty space to pan, drag a node to move it, scroll to
 * zoom toward the cursor, click a node for its receipts.
 */

type Node = {
  id: string;
  label: string;
  kind: "candidate" | "confirmed";
  status: string;
  x: number;
  y: number;
  vx: number;
  vy: number;
  deg: number;
  data: Candidate | Confirmed;
};

const COLORS = {
  ink: "#f4f1ea",
  muted: "#a09992",
  hair: "#2f2b26",
  card: "#1c1a17",
  signal: "#7fa8d8",
  cited: "#6fd3a8",
  unknown: "#e0a23c",
};

function nodeColor(n: Node): string {
  if (n.kind === "confirmed") return COLORS.cited; // merged, indexed truth
  const c = n.data as Candidate;
  if (c.status === "rejected") return COLORS.muted; // no red token on this site; dim instead
  if (c.status === "confirmed_proposal") return COLORS.signal; // a real PR, not yet merged
  return COLORS.muted; // pending / not_sure
}

function sharesPath(a: { affected_paths: string[] }, b: { affected_paths: string[] }): boolean {
  return a.affected_paths.some((p) => b.affected_paths.includes(p));
}

export function DecisionGraph({
  candidates,
  confirmed,
}: {
  candidates: Candidate[];
  confirmed: Confirmed[];
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const nodesRef = useRef<Node[]>([]);
  const linksRef = useRef<[number, number][]>([]);
  const viewRef = useRef({ scale: 1, ox: 0, oy: 0, targetScale: 1 });
  const [selectedId, setSelectedId] = useState<string | null>(null);

  // Local, optimistic copies -- updated in place when an action resolves, so
  // the graph never needs a full server round trip to reflect a confirm.
  const [liveCandidates, setLiveCandidates] = useState(candidates);
  const [signedOut, setSignedOut] = useState(false);

  // Derived from the SOURCE data (props/state), never from nodesRef: the ref
  // is mutated every animation frame outside React's render cycle (position,
  // degree, ...), which is exactly what refs are for, but reading it during
  // render is the real anti-pattern React's lint rule catches here. The
  // detail panel only ever needs the static fields anyway -- label, status,
  // rationale, affected_paths -- never live position.
  const selected: Node | null = useMemo(() => {
    if (!selectedId) return null;
    const c = liveCandidates.find((x) => x.id === selectedId);
    if (c) {
      return { id: c.id, label: c.decision, kind: "candidate", status: c.status,
        x: 0, y: 0, vx: 0, vy: 0, deg: 0, data: c };
    }
    const m = confirmed.find((x) => x.id === selectedId);
    if (m) {
      return { id: m.id, label: m.decision, kind: "confirmed", status: m.status,
        x: 0, y: 0, vx: 0, vy: 0, deg: 0, data: m };
    }
    return null;
  }, [selectedId, liveCandidates, confirmed]);

  // Build nodes + edges once per data change. Seeded in a ring so the force
  // sim starts from a reasonable spread rather than a single point.
  useEffect(() => {
    const nodes: Node[] = [
      ...liveCandidates.map((c) => ({
        id: c.id, label: c.decision, kind: "candidate" as const, status: c.status,
        x: 0, y: 0, vx: 0, vy: 0, deg: 0, data: c,
      })),
      ...confirmed.map((c) => ({
        id: c.id, label: c.decision, kind: "confirmed" as const, status: c.status,
        x: 0, y: 0, vx: 0, vy: 0, deg: 0, data: c,
      })),
    ];
    const links: [number, number][] = [];
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        if (sharesPath(nodes[i].data, nodes[j].data)) {
          links.push([i, j]);
          nodes[i].deg++;
          nodes[j].deg++;
        }
      }
    }
    nodes.forEach((n, i) => {
      const a = (i / Math.max(nodes.length, 1)) * Math.PI * 2;
      n.x = Math.cos(a) * 120 + (Math.random() * 30 - 15);
      n.y = Math.sin(a) * 120 + (Math.random() * 30 - 15);
    });
    nodesRef.current = nodes;
    linksRef.current = links;
  }, [liveCandidates, confirmed]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    let raf = 0;
    let W = 0, H = 0;
    let fitted = false, userInteracted = false, frames = 0;

    function resize() {
      W = canvas!.clientWidth; H = canvas!.clientHeight;
      canvas!.width = W * dpr; canvas!.height = H * dpr;
      ctx!.setTransform(dpr, 0, 0, dpr, 0, 0);
    }
    resize();
    window.addEventListener("resize", resize);

    const radius = (n: Node) => 9 + n.deg * 2.2;
    const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v));

    function tick() {
      const nodes = nodesRef.current, links = linksRef.current;
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const a = nodes[i], b = nodes[j];
          const dx = a.x - b.x, dy = a.y - b.y;
          const d2 = dx * dx + dy * dy || 0.01, d = Math.sqrt(d2);
          const f = 5200 / d2, fx = (dx / d) * f, fy = (dy / d) * f;
          a.vx += fx; a.vy += fy; b.vx -= fx; b.vy -= fy;
        }
      }
      links.forEach(([ai, bi]) => {
        const a = nodes[ai], b = nodes[bi];
        const dx = b.x - a.x, dy = b.y - a.y;
        const d = Math.hypot(dx, dy) || 0.01;
        const f = (d - 135) * 0.02, fx = (dx / d) * f, fy = (dy / d) * f;
        a.vx += fx; a.vy += fy; b.vx -= fx; b.vy -= fy;
      });
      nodes.forEach((n) => {
        if (n === dragNode) return;
        n.vx += (W / 2 - n.x) * 0.0016; n.vy += (H / 2 - n.y) * 0.0016;
        n.vx *= 0.86; n.vy *= 0.86; n.x += n.vx; n.y += n.vy;
      });
    }

    function fitView() {
      const nodes = nodesRef.current;
      if (nodes.length === 0) return;
      let a = 1e9, b = 1e9, c = -1e9, d = -1e9;
      nodes.forEach((n) => {
        const r = radius(n) + 40;
        a = Math.min(a, n.x - r); c = Math.max(c, n.x + r);
        b = Math.min(b, n.y - r); d = Math.max(d, n.y + r);
      });
      const s = clamp(Math.min(W / (c - a), H / (d - b)) * 0.92, 0.4, 1.3);
      const v = viewRef.current;
      v.scale = v.targetScale = s;
      v.ox = W / 2 - ((a + c) / 2) * s; v.oy = H / 2 - ((b + d) / 2) * s;
    }

    let hover: Node | null = null;
    function draw() {
      const nodes = nodesRef.current, links = linksRef.current, v = viewRef.current;
      ctx!.clearRect(0, 0, W, H);
      ctx!.save(); ctx!.translate(v.ox, v.oy); ctx!.scale(v.scale, v.scale);
      const near = new Set<number>();
      if (hover) {
        near.add(nodes.indexOf(hover));
        links.forEach(([a, b]) => {
          if (nodes[a] === hover) near.add(b);
          if (nodes[b] === hover) near.add(a);
        });
      }
      links.forEach(([ai, bi]) => {
        const a = nodes[ai], b = nodes[bi];
        const on = hover && near.has(ai) && near.has(bi);
        ctx!.strokeStyle = on ? "rgba(127,168,216,.6)" : hover ? "rgba(255,255,255,.05)" : "rgba(255,255,255,.11)";
        ctx!.lineWidth = (on ? 1.8 : 1) / v.scale;
        ctx!.beginPath(); ctx!.moveTo(a.x, a.y); ctx!.lineTo(b.x, b.y); ctx!.stroke();
      });
      const showLabels = v.scale > 0.5;
      nodes.forEach((n, i) => {
        const r = radius(n);
        const dim = hover && !near.has(i);
        const sel = n.id === selectedId;
        const dimmed = n.kind === "candidate" && (n.data as Candidate).status === "rejected";
        ctx!.globalAlpha = dimmed ? 0.32 : dim ? 0.35 : 1;
        ctx!.beginPath(); ctx!.arc(n.x, n.y, r, 0, 7);
        ctx!.fillStyle = nodeColor(n);
        ctx!.shadowColor = nodeColor(n); ctx!.shadowBlur = sel ? 24 : near.has(i) ? 16 : 8;
        ctx!.fill(); ctx!.shadowBlur = 0;
        ctx!.lineWidth = (sel ? 2.5 : 1.2) / v.scale;
        ctx!.strokeStyle = sel ? "#fff" : "rgba(255,255,255,.5)"; ctx!.stroke();
        if (showLabels || near.has(i)) {
          ctx!.globalAlpha = dimmed ? 0.3 : dim ? 0.3 : 1;
          ctx!.fillStyle = COLORS.ink; ctx!.font = `600 ${12 / v.scale}px system-ui, sans-serif`;
          ctx!.textAlign = "center"; ctx!.textBaseline = "top";
          const label = n.label.length > 42 ? n.label.slice(0, 40) + "…" : n.label;
          ctx!.shadowColor = "rgba(0,0,0,.9)"; ctx!.shadowBlur = 6;
          ctx!.fillText(label, n.x, n.y + r + 5 / v.scale); ctx!.shadowBlur = 0;
        }
        ctx!.globalAlpha = 1;
      });
      ctx!.restore();
    }

    function frame() {
      tick(); frames++;
      if (!fitted && !userInteracted && frames > 40) { fitView(); fitted = true; }
      const v = viewRef.current;
      if (Math.abs(v.targetScale - v.scale) > 0.0004) {
        const wx = (zoomAnchor.x - v.ox) / v.scale, wy = (zoomAnchor.y - v.oy) / v.scale;
        v.scale += (v.targetScale - v.scale) * 0.22;
        v.ox = zoomAnchor.x - wx * v.scale; v.oy = zoomAnchor.y - wy * v.scale;
      }
      draw();
      raf = requestAnimationFrame(frame);
    }

    let mode: "idle" | "node" | "pan" = "idle";
    let dragNode: Node | null = null;
    let panStart = { x: 0, y: 0, ox: 0, oy: 0 };
    let moved = false;
    let zoomAnchor = { x: 0, y: 0 };

    function toWorld(px: number, py: number) {
      const v = viewRef.current;
      return { x: (px - v.ox) / v.scale, y: (py - v.oy) / v.scale };
    }
    function pick(px: number, py: number): Node | null {
      const w = toWorld(px, py);
      let best: Node | null = null, bd = 1e9;
      nodesRef.current.forEach((n) => {
        const d = Math.hypot(n.x - w.x, n.y - w.y);
        if (d < radius(n) + 8 && d < bd) { bd = d; best = n; }
      });
      return best;
    }
    function localXY(e: PointerEvent) {
      const rect = canvas!.getBoundingClientRect();
      return { x: e.clientX - rect.left, y: e.clientY - rect.top };
    }

    function onDown(e: PointerEvent) {
      userInteracted = true; moved = false;
      canvas!.setPointerCapture(e.pointerId);
      const { x, y } = localXY(e);
      const n = pick(x, y);
      if (n) { mode = "node"; dragNode = n; } else {
        mode = "pan"; panStart = { x: e.clientX, y: e.clientY, ox: viewRef.current.ox, oy: viewRef.current.oy };
      }
    }
    function onMove(e: PointerEvent) {
      const { x, y } = localXY(e);
      if (mode === "node" && dragNode) {
        const w = toWorld(x, y);
        dragNode.x = w.x; dragNode.y = w.y; dragNode.vx = 0; dragNode.vy = 0; moved = true;
        return;
      }
      if (mode === "pan") {
        viewRef.current.ox = panStart.ox + (e.clientX - panStart.x);
        viewRef.current.oy = panStart.oy + (e.clientY - panStart.y);
        moved = true;
        return;
      }
      hover = pick(x, y);
      canvas!.style.cursor = hover ? "pointer" : "grab";
    }
    function onUp() {
      if (mode === "node" && !moved && dragNode) setSelectedId(dragNode.id);
      else if (mode === "pan" && !moved) setSelectedId(null);
      mode = "idle"; dragNode = null;
    }
    function onWheel(e: WheelEvent) {
      e.preventDefault(); userInteracted = true;
      const dy = Math.max(-100, Math.min(100, e.deltaY));
      viewRef.current.targetScale = clamp(viewRef.current.targetScale * Math.exp(-dy * 0.0011), 0.35, 3);
      const rect = canvas!.getBoundingClientRect();
      zoomAnchor = { x: e.clientX - rect.left, y: e.clientY - rect.top };
    }

    canvas.addEventListener("pointerdown", onDown);
    canvas.addEventListener("pointermove", onMove);
    canvas.addEventListener("pointerup", onUp);
    canvas.addEventListener("wheel", onWheel, { passive: false });
    frame();

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
      canvas.removeEventListener("pointerdown", onDown);
      canvas.removeEventListener("pointermove", onMove);
      canvas.removeEventListener("pointerup", onUp);
      canvas.removeEventListener("wheel", onWheel);
    };
    // liveCandidates/confirmed changes rebuild nodesRef above; this effect
    // owns the animation loop and only needs to run once.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function act(
    candidateId: string,
    selection: "recommended" | "reject" | "other",
    otherText?: string,
  ) {
    const res = await fetch("/api/decisions/confirm", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        candidate_id: candidateId,
        selection,
        ...(otherText ? { other_text: otherText } : {}),
      }),
    });
    if (res.status === 401) { setSignedOut(true); return; }
    const result = await res.json();
    if (!res.ok) return;
    setLiveCandidates((prev) => prev.map((c) => (c.id === candidateId ? { ...c, ...result } : c)));
  }

  if (signedOut) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="font-mono text-sm text-unknown">Your sign-in expired. Reload to sign in again.</p>
      </div>
    );
  }

  return (
    <div className="relative h-screen w-full">
      <canvas ref={canvasRef} className="h-full w-full touch-none" />
      <p className="pointer-events-none fixed bottom-5 left-1/2 -translate-x-1/2 font-mono text-[11px] text-muted">
        drag empty space to pan · drag a node to move it · scroll to zoom · click for detail
      </p>
      {liveCandidates.length === 0 && confirmed.length === 0 && (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
          <p className="max-w-sm text-center text-lg text-muted">
            No decisions yet for this repository. They will appear here the next time your
            coding agent recommends one.
          </p>
        </div>
      )}
      {selected && (
        <DetailPanel node={selected} onClose={() => setSelectedId(null)} onAct={act} />
      )}
    </div>
  );
}

function DetailPanel({
  node,
  onClose,
  onAct,
}: {
  node: Node;
  onClose: () => void;
  onAct: (id: string, selection: "recommended" | "reject" | "other", otherText?: string) => void;
}) {
  const [showOther, setShowOther] = useState(false);
  const [otherText, setOtherText] = useState("");

  const isCandidate = node.kind === "candidate";
  const c = isCandidate ? (node.data as Candidate) : null;
  const m = !isCandidate ? (node.data as Confirmed) : null;
  const pending = c && (c.status === "pending" || c.status === "not_sure");

  return (
    <aside className="glass glass-sm fixed right-0 top-0 h-full w-[380px] max-w-[88vw] overflow-y-auto p-6">
      <button
        onClick={onClose}
        aria-label="Close"
        className="absolute right-4 top-4 text-xl leading-none text-muted hover:text-ink"
      >
        ✕
      </button>
      <span
        className="font-mono text-[10.5px] font-bold uppercase tracking-[0.06em]"
        style={{ color: nodeColor(node) }}
      >
        {isCandidate ? c!.status.replace("_", " ") : m!.status.replace(/_/g, " ")}
      </span>
      <h2 className="mt-3 text-lg font-semibold leading-snug text-ink">{node.label}</h2>

      {isCandidate && c!.rationale && (
        <>
          <div className="mt-5 font-mono text-[10.5px] uppercase tracking-[0.12em] text-muted">Why</div>
          <p className="mt-2 text-[13px] leading-relaxed text-muted">{c!.rationale}</p>
        </>
      )}
      {!isCandidate && m!.rationale && (
        <>
          <div className="mt-5 font-mono text-[10.5px] uppercase tracking-[0.12em] text-muted">Why</div>
          <p className="mt-2 text-[13px] leading-relaxed text-muted">{m!.rationale}</p>
        </>
      )}

      {node.data.affected_paths.length > 0 && (
        <>
          <div className="mt-5 font-mono text-[10.5px] uppercase tracking-[0.12em] text-muted">
            Affected paths
          </div>
          <div className="mt-2 flex flex-col gap-1.5">
            {node.data.affected_paths.map((p) => (
              <span key={p} className="rounded-md bg-white/5 px-2.5 py-1.5 font-mono text-[11px] text-ink">
                {p}
              </span>
            ))}
          </div>
        </>
      )}

      {!isCandidate && m!.citation_url && (
        <a
          href={m!.citation_url}
          target="_blank"
          rel="noreferrer"
          className="mt-4 inline-block font-mono text-[12px] font-semibold text-cited"
        >
          ↗ view merged, cited record
        </a>
      )}
      {!isCandidate && !m!.citation_url && m!.pull_request_url && (
        <a
          href={m!.pull_request_url}
          target="_blank"
          rel="noreferrer"
          className="mt-4 inline-block font-mono text-[12px] font-semibold text-signal"
        >
          ↗ view pull request
        </a>
      )}
      {isCandidate && c!.status === "confirmed_proposal" && c!.proposal && (
        <a
          href={c!.proposal.pull_request_url}
          target="_blank"
          rel="noreferrer"
          className="mt-4 inline-block font-mono text-[12px] font-semibold text-signal"
        >
          ↗ view pull request
        </a>
      )}
      {isCandidate && c!.status === "rejected" && (
        <p className="mt-4 font-mono text-[12px] text-muted">
          ✕ Rejected — this recommendation won&apos;t become project memory.
        </p>
      )}

      {pending && (
        <>
          <div className="mt-6 font-mono text-[10.5px] uppercase tracking-[0.12em] text-muted">
            Your call
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            <button
              onClick={() => onAct(c!.id, "recommended")}
              className="rounded-full bg-cited px-4 py-2 text-[13px] font-semibold text-deep transition hover:brightness-110"
            >
              Accept
            </button>
            <button
              onClick={() => onAct(c!.id, "reject")}
              className="rounded-full border border-hair px-4 py-2 text-[13px] font-semibold text-muted transition hover:text-ink"
            >
              Reject
            </button>
            <button
              onClick={() => setShowOther((v) => !v)}
              className="rounded-full border border-hair px-4 py-2 text-[13px] font-semibold text-muted transition hover:text-ink"
            >
              Other…
            </button>
          </div>
          {showOther && (
            <div className="mt-3 flex flex-col gap-2">
              <textarea
                value={otherText}
                onChange={(e) => setOtherText(e.target.value)}
                placeholder="Write the decision in your own words…"
                className="min-h-[80px] rounded-md border border-hair bg-white/5 p-2.5 text-[13px] text-ink outline-none focus:border-signal"
              />
              <button
                onClick={() => otherText.trim() && onAct(c!.id, "other", otherText)}
                disabled={!otherText.trim()}
                className="self-start rounded-full bg-cited px-4 py-2 text-[13px] font-semibold text-deep disabled:opacity-50"
              >
                Add to Icarus
              </button>
            </div>
          )}
        </>
      )}
    </aside>
  );
}
