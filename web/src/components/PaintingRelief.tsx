"use client";

import { useEffect, useRef } from "react";
import * as THREE from "three";

/**
 * A painting as relief, not as wallpaper.
 *
 * The plane is subdivided and every vertex is pushed along z by the luminance
 * of the pixel above it, so the picture acquires real depth: sky and haze sit
 * back, the dark rock and figures stand forward. With a live camera and pointer
 * parallax the surface then moves against itself the way a relief does, which
 * a flat background-image cannot fake at any opacity.
 *
 * Luminance is a PROXY for depth, not a depth map. It is honest about what it
 * is: on these four paintings the bright half really is the distant half (sky,
 * sea-haze) and the dark half really is the near half (rock, bodies, ground),
 * which is why it reads correctly here and would not on an arbitrary image.
 */
export default function PaintingRelief({
  src,
  className,
  strength = 0.55,
  tint = 0.24,
}: {
  src: string;
  className?: string;
  strength?: number;
  tint?: number;
}) {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const cvs = ref.current;
    if (!cvs) return;
    let raf = 0;
    let disposed = false;

    const still =
      typeof window !== "undefined" &&
      window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

    const renderer = new THREE.WebGLRenderer({ canvas: cvs, alpha: true, antialias: true });
    renderer.setClearColor(0x000000, 0);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.6));

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(42, 1, 0.1, 60);
    camera.position.z = 9;

    let mesh: THREE.Mesh | null = null;
    const uniforms = {
      map: { value: null as THREE.Texture | null },
      strength: { value: strength },
      tint: { value: tint },
      t: { value: 0 },
    };

    new THREE.TextureLoader().load(src, (tex) => {
      if (disposed) return;
      tex.colorSpace = THREE.SRGBColorSpace;
      uniforms.map.value = tex;

      const geo = new THREE.PlaneGeometry(16, 9, 190, 110);
      const mat = new THREE.ShaderMaterial({
        uniforms,
        transparent: true,
        depthWrite: false,
        vertexShader: `
          uniform sampler2D map;
          uniform float strength;
          uniform float t;
          varying vec2 vUv;
          varying float vDepth;
          void main() {
            vUv = uv;
            vec3 c = texture2D(map, uv).rgb;
            float lum = dot(c, vec3(0.2126, 0.7152, 0.0722));
            // bright = far, dark = near. Breathing is tiny on purpose: this is
            // stone and weather, not a flag.
            float breathe = 1.0 + sin(t * 0.32 + uv.x * 2.4) * 0.045;
            vDepth = lum;
            vec3 p = position;
            p.z += (0.5 - lum) * strength * 6.0 * breathe;
            gl_Position = projectionMatrix * modelViewMatrix * vec4(p, 1.0);
          }`,
        fragmentShader: `
          precision mediump float;
          uniform sampler2D map;
          uniform float tint;
          varying vec2 vUv;
          varying float vDepth;
          void main() {
            vec3 c = texture2D(map, vUv).rgb;
            c *= 0.72;
            float l = dot(c, vec3(0.2126, 0.7152, 0.0722));
            c = mix(vec3(l), c, 0.38);
            // warm it toward the page's sun so the plate belongs to this site
            c = mix(c, c * vec3(1.28, 1.02, 0.72), tint);
            // near things stay, far things dissolve into the page
            float a = smoothstep(0.94, 0.30, vDepth) * 0.85;
            // and the edges never end in a hard rectangle
            a *= smoothstep(0.0, 0.16, vUv.x) * smoothstep(1.0, 0.84, vUv.x);
            a *= smoothstep(0.0, 0.14, vUv.y) * smoothstep(1.0, 0.86, vUv.y);
            gl_FragColor = vec4(c, a);
          }`,
      });
      mesh = new THREE.Mesh(geo, mat);
      scene.add(mesh);
      resize();
      render();
      if (!still) raf = requestAnimationFrame(loop);
    });

    const resize = () => {
      const w = cvs.clientWidth, h = cvs.clientHeight;
      if (!w || !h) return;
      renderer.setSize(w, h, false);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      if (mesh) {
        // cover: the relief always fills its band, whatever the viewport does
        const visH = 2 * camera.position.z * Math.tan((camera.fov * Math.PI / 180) / 2);
        const visW = visH * camera.aspect;
        const s = Math.max(visW / 16, visH / 9) * 1.08;
        mesh.scale.setScalar(s);
      }
    };
    const render = () => renderer.render(scene, camera);
    window.addEventListener("resize", resize);

    let px = 0, py = 0, tx = 0, ty = 0;
    const onPointer = (e: PointerEvent) => {
      tx = (e.clientX / window.innerWidth - 0.5) * 2;
      ty = (e.clientY / window.innerHeight - 0.5) * 2;
    };
    if (!still) window.addEventListener("pointermove", onPointer, { passive: true });

    let t0: number | null = null;
    const loop = (ts: number) => {
      if (t0 === null) t0 = ts;
      const t = (ts - t0) / 1000;
      uniforms.t.value = t;
      px += (tx - px) * 0.04;
      py += (ty - py) * 0.04;
      if (mesh) {
        // the relief turns toward the cursor; depth does the rest
        mesh.rotation.y = px * 0.13;
        mesh.rotation.x = -py * 0.08;
      }
      render();
      raf = requestAnimationFrame(loop);
    };

    return () => {
      disposed = true;
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
      window.removeEventListener("pointermove", onPointer);
      renderer.dispose();
    };
  }, [src, strength, tint]);

  return <canvas ref={ref} aria-hidden className={className} />;
}
