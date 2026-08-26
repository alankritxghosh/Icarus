"use client";

import { useEffect, useRef } from "react";
import * as THREE from "three";
import { buildIcarus } from "./icarusFigure";

export type Cite = { ref?: string } | string;

/**
 * The evidence graph: a real render of what Icarus indexed for simonw/llm --
 * 2,599 nodes, 934 edges -- precomputed by site/build/build_graph.py straight
 * out of evals/entities.py, where every edge carries the indexed chunk that
 * proves it. Nothing here is inferred and nothing is invented.
 *
 * Co-occurrence edges are excluded at build time. Rendering 2,372 "a later PR
 * touched the same file" links would look impressive and mean nothing, which
 * is the one failure mode this whole feature is supposed to avoid.
 */
export default function EvidenceGraph({
  cited,
  searched,
  className,
}: {
  cited?: Cite[] | null;
  searched?: Cite[] | null;
  className?: string;
}) {
  // The graph is pushed off-centre on wide screens so it occupies the empty
  // half rather than sitting behind the copy, where the legibility wash has to
  // erase it to keep the headline readable. On narrow screens there is no
  // empty half, so it stays centred and the wash carries it instead.
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const lightRef = useRef<((c?: Cite[] | null, s?: Cite[] | null) => void) | null>(null);

  useEffect(() => {
    const cvs = canvasRef.current;
    if (!cvs) return;
    let disposed = false;
    let raf = 0;

    const still =
      typeof window !== "undefined" &&
      window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

    (async () => {
      const g = await fetch("/graph.json").then((r) => r.json());
      if (disposed) return;

      const N: number = g.ids.length;
      const renderer = new THREE.WebGLRenderer({ canvas: cvs, alpha: true, antialias: true });
      renderer.setClearColor(0x000000, 0);
      const dpr = Math.min(window.devicePixelRatio || 1, 1.75);
      renderer.setPixelRatio(dpr);

      const scene = new THREE.Scene();
      const camera = new THREE.PerspectiveCamera(66, 1, 0.1, 20);
      camera.position.z = 3.2;

      const pos = new Float32Array(N * 3);
      for (let i = 0; i < N * 3; i++) pos[i] = g.pos[i] / 1000;
      const kind = new Float32Array(g.node_kind);
      const state = new Float32Array(N); // 0 idle · 1 searched · 2 cited

      // Degree is computed here, not shipped. Most of the corpus is genuinely
      // unlinked, so drawing every node at one size renders that truth as
      // uniform dust and buries the structure that IS there.
      const degree = new Float32Array(N);
      for (let i = 0; i < g.edges.length; i++) degree[g.edges[i]] += 1;
      let maxDeg = 1;
      for (let i = 0; i < N; i++) if (degree[i] > maxDeg) maxDeg = degree[i];
      for (let i = 0; i < N; i++) degree[i] = Math.sqrt(degree[i] / maxDeg);

      const stateAttr = new THREE.BufferAttribute(state, 1);
      stateAttr.setUsage(THREE.DynamicDrawUsage);
      const posAttr = new THREE.BufferAttribute(pos, 3);
      const kindAttr = new THREE.BufferAttribute(kind, 1);
      const degAttr = new THREE.BufferAttribute(degree, 1);

      const points = new THREE.BufferGeometry();
      points.setAttribute("position", posAttr);
      points.setAttribute("kind", kindAttr);
      points.setAttribute("deg", degAttr);
      points.setAttribute("state", stateAttr);

      const lines = new THREE.BufferGeometry();
      lines.setAttribute("position", posAttr);
      lines.setAttribute("kind", kindAttr);
      lines.setAttribute("deg", degAttr);
      lines.setAttribute("state", stateAttr);
      lines.setIndex(new THREE.BufferAttribute(new Uint32Array(g.edges), 1));

      const VERT = `
        attribute float kind; attribute float state; attribute float deg;
        varying float vKind; varying float vState; varying float vDeg;
        uniform float dpr;
        void main() {
          vKind = kind; vState = state; vDeg = deg;
          vec4 mv = modelViewMatrix * vec4(position, 1.0);
          gl_Position = projectionMatrix * mv;
          float base = state > 1.5 ? 20.0 : state > 0.5 ? 14.0 : mix(6.0, 16.0, deg);
          gl_PointSize = (base * dpr) / max(-mv.z, 0.25);
        }`;

      // Colours are the page's own tokens: cited #6FD3A8, searched #E0A23C.
      // A node's colour is a claim about what happened to it, so it must never
      // drift from what the answer card says.
      const FRAG = `
        precision mediump float;
        varying float vKind; varying float vState; varying float vDeg;
        uniform float isLine;
        void main() {
          // Warm neutrals with one cool blue for code. The earlier set was
          // blue-violet across the board, which is where the purple cast on
          // the whole page came from -- 2,599 points is a lot of tint.
          vec3 col = vec3(0.55, 0.60, 0.68);                                  // code
          if (vKind > 0.5 && vKind < 1.5) col = vec3(0.58, 0.55, 0.50);       // commit
          else if (vKind > 1.5 && vKind < 2.5) col = vec3(0.64, 0.58, 0.48);  // issue
          else if (vKind > 2.5) col = vec3(0.72, 0.62, 0.46);                 // pr
          float a = isLine > 0.5 ? 0.34 : mix(0.42, 1.0, vDeg);
          if (vState > 1.5) { col = vec3(0.435,0.827,0.659); a = isLine > 0.5 ? 0.85 : 1.0; }
          else if (vState > 0.5) { col = vec3(0.878,0.635,0.235); a = isLine > 0.5 ? 0.55 : 0.95; }
          if (isLine < 0.5) {
            vec2 d = gl_PointCoord - vec2(0.5);
            float r = dot(d, d);
            if (r > 0.25) discard;
            a *= smoothstep(0.25, 0.06, r);
          }
          gl_FragColor = vec4(col, a);
        }`;

      const mat = (isLine: number) =>
        new THREE.ShaderMaterial({
          uniforms: { dpr: { value: dpr }, isLine: { value: isLine } },
          vertexShader: VERT,
          fragmentShader: FRAG,
          transparent: true,
          depthTest: false,
          depthWrite: false,
          // Additive: 2,599 points overlap heavily, and source-alpha blending
          // flattened the cloud into a uniform haze.
          blending: THREE.AdditiveBlending,
        });

      const cloud = new THREE.Points(points, mat(0));
      const wires = new THREE.LineSegments(lines, mat(1));
      cloud.frustumCulled = wires.frustumCulled = false;
      // The graph draws first and ignores depth (additive, depthTest off), so
      // the figure has to come after it or it would be painted over.
      cloud.renderOrder = -1;
      wires.renderOrder = -2;
      const world = new THREE.Group();
      world.add(wires, cloud);
      scene.add(world);

      // ---- Icarus ------------------------------------------------------------
      // Real geometry, not a plate: six feathers a wing, each on its own pivot,
      // rebuilt from the Mac app's parametric mark.
      const icarus = buildIcarus();
      icarus.group.renderOrder = 1;
      scene.add(icarus.group);

      // One sun, high and to the right, plus a cold rim so the far edge does not
      // disappear into the page. Ambient is low: he should be lit, not floodlit.
      const sun = new THREE.DirectionalLight(0xffd9a0, 2.6);
      sun.position.set(2.4, 3.2, 2.0);
      const rim = new THREE.DirectionalLight(0x9fc0e0, 0.75);
      rim.position.set(-2.6, -0.6, -1.8);
      scene.add(sun, rim, new THREE.AmbientLight(0x4a4640, 0.9));

      let icarusScale = 1;
      let icarusBaseX = 0;
      let icarusBaseY = 0;
      const resize = () => {
        const w = cvs.clientWidth, h = cvs.clientHeight;
        if (!w || !h) return;
        renderer.setSize(w, h, false);
        camera.aspect = w / h;
        camera.updateProjectionMatrix();
        // Slide toward the open right-hand column, and pull the camera back a
        // little there so the cloud reads as a whole object rather than a
        // cropped edge.
        const wide = w >= 1024;
        world.position.x = wide ? 0.95 : 0;
        camera.position.z = wide ? 3.0 : 3.45;
        // Fill the open column rather than floating in the middle of it. The
        // cloud is a unit ball by construction, so this is the only place its
        // on-screen size is decided.
        world.scale.setScalar(wide ? 2.7 : 1.6);
        // Icarus flies in the open half on wide screens; on a phone there is no
        // open half, so he sits high and small above the copy instead.
        // On a phone he was dead centre, directly behind the headline, which
        // is both unreadable and the worst place to put the one thing with
        // life in it. He now flies clear in the upper right, above the copy.
        icarusBaseX = wide ? 1.02 : 0.62;
        icarus.group.position.z = wide ? 0.4 : 0.2;
        // He was flying off the right edge at 1.0 on a 1512px screen.
        icarusScale = wide ? 0.78 : 0.42;
        // High, and higher still on a phone where he sits above the copy
        // rather than beside it.
        icarusBaseY = wide ? 0.42 : 1.34;
      };
      const render = () => renderer.render(scene, camera);
      window.addEventListener("resize", resize);

      // Citations name a WINDOW (code:llm/utils.py#L149-L153); the graph names
      // the FILE. Strip the window, or every code citation silently fails to
      // light -- which looks exactly like the graph working.
      const index: Record<string, number> = Object.create(null);
      for (let i = 0; i < N; i++) index[g.ids[i]] = i;
      const nodeOf = (ref?: string) => {
        if (!ref) return -1;
        const r = String(ref).split("#")[0];
        if (r in index) return index[r];
        if (!/^[a-z]+:/.test(r) && "code:" + r in index) return index["code:" + r];
        return -1;
      };
      lightRef.current = (c, s) => {
        state.fill(0);
        const mark = (list: Cite[] | null | undefined, v: number) =>
          (list || []).forEach((x) => {
            const i = nodeOf(typeof x === "string" ? x : x?.ref);
            if (i >= 0) state[i] = v;
          });
        mark(s, 1);
        mark(c, 2); // cited wins wherever both apply
        stateAttr.needsUpdate = true;
        if (still) render();
      };

      let px = 0, py = 0, tx = 0, ty = 0;
      const onPointer = (e: PointerEvent) => {
        tx = (e.clientX / window.innerWidth - 0.5) * 2;
        ty = (e.clientY / window.innerHeight - 0.5) * 2;
      };
      if (!still) window.addEventListener("pointermove", onPointer, { passive: true });

      icarus.update(0.85);          // a pose mid-upstroke, not a T-pose
      resize();
      icarus.group.position.x = icarusBaseX;
      icarus.group.position.y += icarusBaseY;
      icarus.group.scale.setScalar(0.026 * icarusScale);
      // Draw one frame immediately, always. requestAnimationFrame does not fire
      // in a background tab, so a graph that only painted from the loop stayed
      // blank until the tab was focused -- found live, not reasoned about.
      render();

      if (!still) {
        let t0: number | null = null;
        const loop = (ts: number) => {
          if (t0 === null) t0 = ts;
          px += (tx - px) * 0.045;
          py += (ty - py) * 0.045;
          const t = (ts - t0) / 1000;
          world.rotation.y = t * 0.045 + px * 0.16;
          world.rotation.x = py * 0.1;
          icarus.update(t);
          // Parallax rides on top of the flight animation. Absolute, not `+=`:
          // update() only rewrites y, so an accumulating x drifts him off screen
          // a few seconds in.
          icarus.group.position.x = icarusBaseX - px * 0.10;
          icarus.group.position.y += icarusBaseY - py * 0.06;
          icarus.group.scale.setScalar(0.026 * icarusScale);
          render();
          raf = requestAnimationFrame(loop);
        };
        raf = requestAnimationFrame(loop);
      }

      return () => {
        window.removeEventListener("resize", resize);
        window.removeEventListener("pointermove", onPointer);
      };
    })().catch(() => {
      /* No WebGL, no graph.json, or a parse error: the section renders without
         it. The graph is an upgrade, never a dependency. */
    });

    return () => {
      disposed = true;
      cancelAnimationFrame(raf);
    };
  }, []);

  useEffect(() => {
    lightRef.current?.(cited, searched);
  }, [cited, searched]);

  return <canvas ref={canvasRef} aria-hidden className={className} />;
}
