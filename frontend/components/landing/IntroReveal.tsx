import { motion, useMotionValueEvent, useReducedMotion, useScroll, useSpring, useTransform } from "motion/react";
import { useEffect, useMemo, useRef, useState, useSyncExternalStore, type ReactNode } from "react";

const subscribeNoop = () => () => {};

/**
 * Cinematic opening: a clean editorial cover (© 2026 · orange mesh pill · MindMesh).
 * Scrolling grows the pill to full screen, then it fades into the real site.
 * Only a tiny overlay animates (no clip-path on the page) so it stays smooth.
 */
function Mesh() {
  const paths = useMemo(() => {
    const out: string[] = [];
    for (let i = 0; i < 18; i++) {
      const base = 6 + i * 5.2;
      let d = `M -10 ${base}`;
      for (let x = -10; x <= 410; x += 10) {
        const y = base + Math.sin(x / 38 + i * 0.55) * 4 + Math.sin(x / 17 + i) * 1.6;
        d += ` L ${x} ${y.toFixed(2)}`;
      }
      out.push(d);
    }
    return out;
  }, []);
  return (
    <svg viewBox="0 0 400 100" preserveAspectRatio="xMidYMid slice" className="absolute inset-0 h-full w-full">
      <rect width="400" height="100" className="fill-orange" />
      {paths.map((d, i) => (
        <path key={i} d={d} fill="none" strokeWidth="0.9" className="stroke-ink" opacity={0.18 + (i % 3) * 0.08} />
      ))}
    </svg>
  );
}

export function IntroReveal({ children }: { children: ReactNode }) {
  const reduce = useReducedMotion();
  const [size, setSize] = useState({ w: 1280, h: 800 });
  const held = useRef(false);
  // The intro plays on every visit to the landing page. The only skip is a
  // deep link (/#features) — that must land on its section, not the cover.
  const deepLink = useSyncExternalStore(
    subscribeNoop,
    () => window.location.hash !== "",
    () => false,
  );

  useEffect(() => {
    const update = () => setSize({ w: window.innerWidth, h: window.innerHeight });
    update();
    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, []);

  const { w, h } = size;
  const D = h * 2;
  const { scrollY } = useScroll();
  const raw = useTransform(scrollY, (s) => Math.min(1, Math.max(0, s / D)));
  const p = useSpring(raw, { stiffness: 140, damping: 32, mass: 0.5, restDelta: 0.0005 });
  const e = useTransform(p, (v) => (v < 0.5 ? 2 * v * v : 1 - Math.pow(-2 * v + 2, 2) / 2));

  const pw0 = Math.min(w * 0.26, 340);
  const ph0 = Math.min(h * 0.11, 92);
  const grow = useTransform(e, [0, 0.82], [0, 1], { clamp: true });
  const pillW = useTransform(grow, (g) => pw0 + (w - pw0) * g);
  const pillH = useTransform(grow, (g) => ph0 + (h - ph0) * g);
  const pillR = useTransform(grow, (g) => 999 * Math.pow(1 - g, 3));
  const inset = useTransform(e, (v) => 0.03 * Math.min(w, h) * Math.max(0, 1 - v * 1.25));
  const sideOpacity = useTransform(p, [0, 0.16], [1, 0]);
  const leftX = useTransform(p, [0, 0.2], [0, -w * 0.12]);
  const rightX = useTransform(p, [0, 0.2], [0, w * 0.12]);
  const layerOpacity = useTransform(p, [0.82, 0.98], [1, 0]);
  const layerVis = useTransform(layerOpacity, (o) => (o <= 0.001 ? "hidden" : "visible"));
  const siteScale = useTransform(e, [0.7, 1], [0.96, 1]);
  // the orange mesh dissolves early so the live site shows through the growing window
  const meshOpacity = useTransform(p, [0.08, 0.4], [1, 0]);
  const pillBorder = useTransform(grow, [0.8, 1], [2, 0]);

  // keep the site pinned while the cover zooms
  const y = useTransform(scrollY, (s) => (s < D ? s : D) - D);

  useMotionValueEvent(raw, "change", (v) => {
    if (v >= 0.999 && !held.current) {
      held.current = true;
      window.dispatchEvent(new CustomEvent("mindmesh:intro-hold", { detail: 2000 }));
    }
    if (v < 0.5) held.current = false;
  });

  if (reduce || deepLink) return <div className="bg-paper">{children}</div>;

  return (
    <>
      <motion.div
        aria-hidden="true"
        style={{ opacity: layerOpacity, visibility: layerVis }}
        className="pointer-events-none fixed inset-0 z-50"
      >
        <motion.div
          style={{ inset, boxShadow: "0 0 0 100vmax var(--ink)" }}
          className="absolute overflow-hidden rounded-[32px]"
        >
          <div className="absolute inset-0 grid place-items-center">
            <motion.div
              style={{ width: pillW, height: pillH, borderRadius: pillR, boxShadow: "0 0 0 200vmax var(--paper-alt)", borderWidth: pillBorder }}
              className="relative overflow-hidden border-ink will-change-[width,height]"
            >
              <motion.div style={{ opacity: meshOpacity }} className="absolute inset-0">
                <Mesh />
              </motion.div>
            </motion.div>
          </div>
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="grid w-full grid-cols-[1fr_auto_1fr] items-center gap-6 sm:gap-10">
              <motion.span style={{ opacity: sideOpacity, x: leftX }} className="justify-self-end font-mono text-sm font-bold text-ink sm:text-lg">
                © 2026
              </motion.span>
              <div style={{ width: pw0 }} />
              <motion.span style={{ opacity: sideOpacity, x: rightX }} className="justify-self-start font-display text-lg uppercase text-ink sm:text-2xl">
                MindMesh
              </motion.span>
            </div>
          </div>
          <motion.p style={{ opacity: sideOpacity }} className="absolute inset-x-0 bottom-[6vmin] text-center font-mono text-[11px] font-bold tracking-widest text-ink-muted">
            SCROLL TO ENTER ↓
          </motion.p>
        </motion.div>
      </motion.div>
      <div style={{ height: D }} aria-hidden="true" />
      <motion.div
        style={{ y, scale: siteScale, transformOrigin: "50% 50vh" }}
        className="relative z-10 bg-paper"
      >
        {children}
      </motion.div>
    </>
  );
}
