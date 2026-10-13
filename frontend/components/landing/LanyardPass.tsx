import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";

// Feel constants (world units, ~112px per unit)
const GRAVITY = -22;
const DRAG = 0.986;
const SEGMENTS = 6;
const SEG_LEN = 0.13;
const STRAP_STIFFNESS = 0.55; // elastic: fraction of stretch corrected per iteration
const MAX_STRETCH = 2.6; // hard limit multiplier of rest length
const CARD_W = 1.0;
const CARD_H = 1.39;
const ITER = 12;
const ANCHOR = new THREE.Vector3(0, 3.6, 0);
const MAX_REACH = SEGMENTS * SEG_LEN * 2.5; // elastic grab limit (~2.5x rest length)
const MAX_TILT = 0.45; // rad — card never turns edge-on

type P = { p: THREE.Vector3; o: THREE.Vector3 };

function readVar(name: string, fallback: string) {
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return v || fallback;
}

function drawCard(canvas: HTMLCanvasElement) {
  const c = canvas.getContext("2d")!;
  const W = canvas.width, H = canvas.height;
  const paper = readVar("--paper-card", "#F5EBDD");
  const ink = readVar("--ink", "#111");
  const muted = readVar("--ink-muted", "#5C4A3A");
  const orange = readVar("--orange", "#FF5C00");
  const sheet = readVar("--sheet", "#FFF6E9");
  c.fillStyle = paper; c.fillRect(0, 0, W, H);
  c.strokeStyle = ink; c.lineWidth = 10; c.strokeRect(5, 5, W - 10, H - 10);
  // slot
  c.fillStyle = sheet; c.beginPath(); c.roundRect(W / 2 - 50, 26, 100, 22, 11); c.fill();
  c.lineWidth = 5; c.stroke();
  // header
  c.fillStyle = orange; c.fillRect(5, 70, W - 10, 90);
  c.fillStyle = ink; c.fillRect(5, 158, W - 10, 5); c.fillRect(5, 68, W - 10, 5);
  c.font = "64px Anton, Impact, sans-serif"; c.textBaseline = "middle";
  c.fillText("MINDMESH", 36, 118);
  c.font = "bold 18px 'JetBrains Mono', monospace";
  c.fillText("v1.4", W - 92, 118);
  // avatar
  c.fillStyle = sheet; c.beginPath(); c.roundRect(36, 200, 180, 210, 22); c.fill();
  c.lineWidth = 6; c.stroke();
  c.fillStyle = ink; c.beginPath(); c.arc(126, 280, 40, 0, Math.PI * 2); c.fill();
  c.beginPath(); c.ellipse(126, 410, 72, 62, 0, Math.PI, 0); c.fill();
  // meta
  c.fillStyle = muted; c.font = "bold 18px 'JetBrains Mono', monospace";
  c.fillText("[ ROLE ]", 240, 220);
  c.fillStyle = ink; c.font = "34px Anton, Impact, sans-serif";
  c.fillText("AI KNOWLEDGE", 240, 262); c.fillText("OS", 240, 300);
  c.fillStyle = muted; c.font = "bold 18px 'JetBrains Mono', monospace";
  c.fillText("[ ID ] MM-0042", 240, 350);
  c.fillText("[ ACCESS ] ALL", 240, 384);
  // tagline
  c.fillStyle = ink; c.font = "44px Anton, Impact, sans-serif";
  c.fillText("BUILDING A", 36, 472); c.fillStyle = orange; c.fillText("BRIGHTER MIND", 36, 522);
  // bars
  const bars = [0.4, 0.7, 0.5, 0.9, 0.6, 1, 0.75, 0.85];
  bars.forEach((b, i) => {
    const h = 90 * b, x = 36 + i * 34;
    c.fillStyle = i % 2 ? orange : ink; c.fillRect(x, 650 - h, 24, h);
  });
  // barcode
  for (let x = 330; x < W - 36; x += 6) { c.fillStyle = ink; c.fillRect(x, 570, (x * 7) % 3 + 1.5, 80); }
  c.fillStyle = ink; c.font = "bold 20px 'JetBrains Mono', monospace";
  c.fillText("TAP TO CONTACT →", 36, 690);
}

function Rig({ onTap }: { onTap: () => void }) {
  const { camera, gl } = useThree();
  const pts = useMemo<P[]>(() => {
    const arr: P[] = [];
    for (let i = 0; i <= SEGMENTS; i++) {
      const v = new THREE.Vector3(ANCHOR.x, ANCHOR.y - i * SEG_LEN, 0);
      arr.push({ p: v.clone(), o: v.clone() });
    }
    // card top & bottom
    const t = arr[SEGMENTS]!.p;
    const b = new THREE.Vector3(t.x + 0.2, t.y - CARD_H, 0);
    arr.push({ p: b.clone(), o: b.clone().add(new THREE.Vector3(0.25, 0, 0)) });
    return arr;
  }, []);
  const card = useRef<THREE.Group>(null);
  const cardMesh = useRef<THREE.Mesh>(null);
  const segs = useRef<(THREE.Mesh | null)[]>([]);
  const drag = useRef<{ on: boolean; target: THREE.Vector3; moved: number; start: THREE.Vector2; t: number }>({
    on: false, target: new THREE.Vector3(), moved: 0, start: new THREE.Vector2(), t: 0,
  });
  const spin = useRef({ y: 0, vy: 0 });

  const texCanvas = useMemo(() => {
    const cv = document.createElement("canvas"); cv.width = 512; cv.height = 720; return cv;
  }, []);
  const tex = useMemo(() => {
    const t = new THREE.CanvasTexture(texCanvas);
    t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 4; return t;
  }, [texCanvas]);

  useEffect(() => {
    const redraw = () => { drawCard(texCanvas); tex.needsUpdate = true; };
    redraw();
    document.fonts?.ready.then(redraw);
    const mo = new MutationObserver(() => requestAnimationFrame(redraw));
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
    return () => mo.disconnect();
  }, [tex, texCanvas]);

  useEffect(() => {
    const ray = new THREE.Raycaster();
    const plane = new THREE.Plane(new THREE.Vector3(0, 0, 1), 0);
    const toWorld = (e: PointerEvent) => {
      const r = gl.domElement.getBoundingClientRect();
      const ndc = new THREE.Vector2(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
      ray.setFromCamera(ndc, camera);
      return ndc;
    };
    const down = (e: PointerEvent) => {
      toWorld(e);
      if (!cardMesh.current || !ray.intersectObject(cardMesh.current).length) return;
      e.preventDefault();
      const hit = new THREE.Vector3(); ray.ray.intersectPlane(plane, hit);
      drag.current.on = true; drag.current.moved = 0; drag.current.t = performance.now();
      drag.current.start.set(e.clientX, e.clientY);
      drag.current.target.copy(hit);
      document.body.style.cursor = "grabbing";
    };
    const move = (e: PointerEvent) => {
      toWorld(e);
      if (drag.current.on) {
        ray.ray.intersectPlane(plane, drag.current.target);
        drag.current.moved = Math.max(drag.current.moved, drag.current.start.distanceTo(new THREE.Vector2(e.clientX, e.clientY)));
      } else if (cardMesh.current) {
        document.body.style.cursor = ray.intersectObject(cardMesh.current).length ? "grab" : "";
      }
    };
    const up = () => {
      if (!drag.current.on) return;
      drag.current.on = false; document.body.style.cursor = "";
      const quick = performance.now() - drag.current.t < 250;
      const still = pts[SEGMENTS]!.p.distanceTo(pts[SEGMENTS]!.o) < 0.03;
      if (drag.current.moved < 6 && quick && still) onTap();
    };
    window.addEventListener("pointerdown", down);
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
    return () => {
      window.removeEventListener("pointerdown", down);
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
    };
  }, [camera, gl, onTap, pts]);

  const tmp = useMemo(() => new THREE.Vector3(), []);
  useFrame((_, raw) => {
    const dt = Math.min(raw, 0.033);
    const top = SEGMENTS;
    // integrate
    for (let i = 1; i < pts.length; i++) {
      const q = pts[i]!;
      tmp.copy(q.p).sub(q.o).multiplyScalar(DRAG);
      q.o.copy(q.p);
      q.p.add(tmp); q.p.y += GRAVITY * dt * dt;
    }
    const lenFor = (i: number) => (i === pts.length - 1 ? CARD_H : SEG_LEN);
    // clamp the grab target to the lanyard's elastic reach
    if (drag.current.on) {
      tmp.copy(drag.current.target).sub(ANCHOR);
      const reach = tmp.length();
      if (reach > MAX_REACH) drag.current.target.copy(ANCHOR).addScaledVector(tmp, MAX_REACH / reach);
    }
    for (let k = 0; k < ITER; k++) {
      pts[0]!.p.copy(ANCHOR);
      if (drag.current.on) {
        // pin the card's grab point (top) toward the pointer
        pts[top]!.p.lerp(drag.current.target, 0.6);
      }
      for (let i = 0; i < pts.length - 1; i++) {
        const a = pts[i]!.p, b = pts[i + 1]!.p;
        const rest = lenFor(i + 1);
        tmp.copy(b).sub(a);
        const d = tmp.length() || 1e-6;
        const card = i + 1 === pts.length - 1;
        let diff: number;
        if (card) diff = (d - rest) / d; // rigid card
        else if (d > rest * MAX_STRETCH) diff = (d - rest * MAX_STRETCH) / d; // hard strain limit
        else diff = ((d - rest) / d) * (d > rest ? STRAP_STIFFNESS : 1); // Hooke elastic stretch
        const wa = i === 0 ? 0 : drag.current.on && i === top ? 0.1 : 0.5;
        const wb = drag.current.on && i + 1 === top ? 0.1 : 1 - wa;
        a.addScaledVector(tmp, diff * wa);
        b.addScaledVector(tmp, -diff * wb);
      }
    }
    // render strap
    for (let i = 0; i < SEGMENTS; i++) {
      const m = segs.current[i]; if (!m) continue;
      const a = pts[i]!.p, b = pts[i + 1]!.p;
      const len = a.distanceTo(b);
      m.position.copy(a).add(b).multiplyScalar(0.5);
      m.rotation.z = Math.atan2(b.y - a.y, b.x - a.x) + Math.PI / 2;
      const strain = len / SEG_LEN;
      m.scale.set(1 / Math.sqrt(Math.max(strain, 1)), len + 0.02, 1); // thins under tension
    }
    // card
    const t = pts[top]!.p, bt = pts[top + 1]!.p;
    const vx = t.x - pts[top]!.o.x;
    // gentle tilt spring — strong face-forward return, clamped so the card never turns edge-on
    spin.current.vy += (-spin.current.y * 90 + vx * 55) * dt;
    spin.current.vy *= Math.exp(-6 * dt);
    spin.current.y = THREE.MathUtils.clamp(spin.current.y + spin.current.vy * dt, -MAX_TILT, MAX_TILT);
    if (card.current) {
      card.current.position.copy(t);
      card.current.rotation.set(0, spin.current.y, Math.atan2(bt.y - t.y, bt.x - t.x) + Math.PI / 2);
    }
  });

  const strapMat = useMemo(() => new THREE.MeshStandardMaterial({ color: "#FF5C00", roughness: 0.7 }), []);
  return (
    <>
      <mesh position={ANCHOR}>
        <cylinderGeometry args={[0.09, 0.09, 0.08, 20]} />
        <meshStandardMaterial color="#9a9a9a" metalness={0.9} roughness={0.25} />
      </mesh>
      {Array.from({ length: SEGMENTS }).map((_, i) => (
        <mesh key={i} ref={(m) => { segs.current[i] = m; }} material={strapMat}>
          <boxGeometry args={[0.1, 1, 0.02]} />
        </mesh>
      ))}
      <group ref={card}>
        <mesh position={[0, 0.05, 0]}>
          <boxGeometry args={[0.22, 0.11, 0.05]} />
          <meshStandardMaterial color="#b5b5b5" metalness={0.85} roughness={0.3} />
        </mesh>
        <mesh ref={cardMesh} position={[0, -CARD_H / 2, 0]}>
          <boxGeometry args={[CARD_W, CARD_H, 0.04]} />
          <meshStandardMaterial attach="material-0" color="#111" />
          <meshStandardMaterial attach="material-1" color="#111" />
          <meshStandardMaterial attach="material-2" color="#111" />
          <meshStandardMaterial attach="material-3" color="#111" />
          <meshPhysicalMaterial attach="material-4" map={tex} roughness={0.55} clearcoat={0.4} />
          <meshPhysicalMaterial attach="material-5" map={tex} roughness={0.55} clearcoat={0.4} />
        </mesh>
      </group>
    </>
  );
}

export default function LanyardPass({ onTap }: { onTap: () => void }) {
  return (
    <div className="pointer-events-none absolute left-1/2 top-full z-40 h-[820px] w-[900px] -translate-x-1/2" aria-hidden="true">
      <Canvas camera={{ position: [0, 0, 10], fov: 40.2 }} dpr={[1, 2]} gl={{ alpha: true, antialias: true }} style={{ pointerEvents: "none" }}>
        <ambientLight intensity={1.6} />
        <directionalLight position={[3, 4, 6]} intensity={1.8} />
        <directionalLight position={[-4, -2, 3]} intensity={0.6} />
        <Rig onTap={onTap} />
      </Canvas>
    </div>
  );
}
