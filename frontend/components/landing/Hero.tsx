import { motion, useReducedMotion, useScroll, useTransform } from "motion/react";
import { useRef } from "react";
import { ArrowRight, Youtube, Instagram, Send } from "lucide-react";
import { Btn, EASE } from "./ui";
import { ParticleHeading } from "./ParticleHeading";

export function Hero() {
  const ref = useRef<HTMLElement>(null);
  const reduceMotion = useReducedMotion();
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start start", "end end"] });
  const terminalScale = useTransform(scrollYProgress, [0, 0.58], reduceMotion ? [1, 1] : [0.82, 1]);
  const terminalY = useTransform(scrollYProgress, [0, 0.58], reduceMotion ? [0, 0] : [120, -18]);
  const terminalOpacity = useTransform(scrollYProgress, [0, 0.22], reduceMotion ? [1, 1] : [0.22, 1]);
  const terminalRotate = useTransform(scrollYProgress, [0.08, 0.62], reduceMotion ? [0, 0] : [10, 0]);
  const copyScale = useTransform(scrollYProgress, [0, 0.48], reduceMotion ? [1, 1] : [1, 0.88]);
  const copyOpacity = useTransform(scrollYProgress, [0, 0.46], reduceMotion ? [1, 1] : [1, 0.16]);

  return (
    <section ref={ref} className="hero-scroll relative">
      <div className="hero-stage sticky top-16 flex h-[calc(100dvh-4rem)] flex-col items-center overflow-hidden px-4 pb-5 pt-6 sm:pt-8">
        <motion.div style={{ opacity: copyOpacity, scale: copyScale }} className="hero-copy flex w-full origin-top flex-col items-center text-center">
          <span className="brut-btn mb-4 rounded-full bg-sheet px-4 py-1.5 font-mono text-[11px] font-bold tracking-widest sm:mb-5">
            <span className="text-orange">●</span> YOUR PERSONAL AI KNOWLEDGE WORKSPACE
          </span>
          <ParticleHeading />
          <motion.p
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, ease: EASE, delay: 0.55 }}
            className="hero-description mt-3 max-w-xl text-base text-ink-muted sm:mt-4 sm:text-lg"
          >
            Save YouTube and Instagram links, ask AI about them, and find everything in your private library.
          </motion.p>
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, ease: EASE, delay: 0.65 }}
            className="hero-actions mt-4 flex flex-wrap justify-center gap-3 sm:mt-5 sm:gap-4"
          >
            <Btn href="/signup">Create Your Account <ArrowRight className="h-4 w-4" /></Btn>
            <Btn variant="paper" href="#how">See How it Works</Btn>
          </motion.div>
        </motion.div>

        <motion.div
          style={{ opacity: terminalOpacity, scale: terminalScale, y: terminalY, rotateX: terminalRotate, transformOrigin: "center top" }}
          className="hero-dashboard mt-5 w-full max-w-7xl shrink-0 overflow-hidden rounded-[clamp(16px,2vw,24px)] border-2 border-ink bg-sheet shadow-[6px_6px_0_var(--ink)] sm:mt-6 md:absolute md:bottom-5 md:mt-0"
        >
          <Dashboard reducedMotion={Boolean(reduceMotion)} />
        </motion.div>
      </div>
    </section>
  );
}

function Dashboard({ reducedMotion }: { reducedMotion: boolean }) {
  const sources = [
    { i: Youtube, l: "Karpathy — LLM intro", s: "Video" },
    { i: Instagram, l: "@designmatters reel", s: "Reel" },
  ];
  const reveal = (delay: number, x = 0, y = 14) => ({
    initial: reducedMotion ? false : { opacity: 0, x, y },
    whileInView: { opacity: 1, x: 0, y: 0 },
    viewport: { once: true, amount: 0.12 },
    transition: { delay, duration: 0.5, ease: EASE },
  });
  return (
    <div className="dashboard-grid grid min-h-0 grid-cols-1 text-sm md:min-h-[360px] md:grid-cols-[minmax(150px,1fr)_minmax(0,2fr)] lg:min-h-[clamp(300px,42vh,430px)] xl:grid-cols-[minmax(190px,1fr)_minmax(360px,2fr)_minmax(180px,1fr)]">
      <div className="grid grid-cols-[auto_minmax(0,1fr)] items-center gap-3 border-b-2 border-ink bg-paper-alt px-3 py-2.5 md:col-span-2 xl:col-span-3 sm:px-4">
        <div className="flex shrink-0 items-center gap-2">
        <span className="h-3 w-3 rounded-full border-2 border-ink bg-orange" />
        <span className="h-3 w-3 rounded-full border-2 border-ink bg-paper-card" />
        <span className="h-3 w-3 rounded-full border-2 border-ink bg-sheet" />
        </div>
        <span className="truncate font-mono text-[10px] text-ink-muted sm:text-xs">Your workspace / Ask AI</span>
      </div>
      <aside className="hidden border-r-2 border-ink bg-paper p-2.5 md:block xl:p-3">
        <p className="mb-2 font-mono text-[10px] font-bold tracking-widest text-ink-muted">STORED SOURCES · 2</p>
        {sources.map(({ i: I, l, s }, index) => (
          <motion.div key={l} {...reveal(0.22 + 0.08 * index, -16, 0)} className="source-item mb-1.5 flex items-center gap-2 rounded-xl border-2 border-ink bg-sheet p-1.5">
            <span className="grid h-6 w-6 shrink-0 place-items-center rounded-lg bg-orange"><I className="h-3.5 w-3.5" /></span>
            <div className="min-w-0">
              <p className="truncate text-xs font-bold">{l}</p>
              <p className="text-[10px] text-ink-muted">{s}</p>
            </div>
          </motion.div>
        ))}
      </aside>
      <div className="chat-column flex min-w-0 flex-col gap-2.5 p-3 sm:p-4 max-sm:min-h-[340px]">
        <motion.div {...reveal(0.35, 18, 0)} className="chat-query max-w-[92%] self-end rounded-2xl border-2 border-ink bg-paper-card px-3 py-2.5 text-xs font-semibold sm:px-4 sm:text-sm">
          What ideas did I save about attention and design?
        </motion.div>
        <motion.div {...reveal(0.58)} className="chat-answer max-w-[96%] rounded-2xl border-2 border-ink bg-sheet p-3 shadow-[3px_3px_0_var(--ink)] sm:p-4">
          <p className="leading-relaxed">
            The YouTube transcript explains how attention relates tokens across a sequence <b className="text-orange">[1]</b>.
            The Instagram Reel you saved adds a visual example of that idea <b className="text-orange">[2]</b>.
          </p>
          <div className="mt-3 flex flex-wrap gap-2 font-mono text-[10px] font-bold">
            {["GROUNDED ANSWER", "[1] YouTube · 04:12", "[2] Instagram Reel"].map((tag, index) => (
              <motion.span key={tag} initial={reducedMotion ? false : { opacity: 0, scale: 0.55 }} whileInView={{ opacity: 1, scale: 1 }} viewport={{ once: true }} transition={{ delay: 0.88 + index * 0.09, type: "spring", stiffness: 280, damping: 18 }} className={`rounded-full border-2 border-ink px-2 py-0.5 ${index === 0 ? "bg-orange" : "bg-paper"}`}>{tag}</motion.span>
            ))}
          </div>
        </motion.div>
        <motion.div {...reveal(1.15, 0, 10)} className="chat-composer mt-auto grid grid-cols-[minmax(0,1fr)_auto] items-center gap-2 rounded-2xl border-2 border-ink bg-paper px-3 py-3 sm:px-4">
          <span className="truncate text-ink-muted">Ask your brain anything…</span>
          <motion.span animate={{ y: [0, -2, 0] }} transition={{ duration: 2, repeat: Infinity, repeatDelay: 2 }} className="grid h-8 w-8 shrink-0 place-items-center rounded-lg border-2 border-ink bg-orange"><Send className="h-4 w-4" /></motion.span>
        </motion.div>
      </div>
      <motion.div {...reveal(0.62, 18, 0)} className="hidden flex-col border-l-2 border-ink bg-paper xl:flex">
        <div className="border-b-2 border-ink p-4">
          <p className="mb-2 font-mono text-[10px] font-bold tracking-widest text-ink-muted">SAVED SOURCES</p>
          <div className="space-y-2">
            {["YouTube video · Ready", "Instagram Reel · Ready"].map((item) => (
              <p key={item} className="rounded-lg border-2 border-ink bg-sheet px-2 py-2 text-xs font-semibold">{item}</p>
            ))}
          </div>
        </div>
        <div className="p-4">
          <p className="mb-2 font-mono text-[10px] font-bold tracking-widest text-ink-muted">YOUR LIBRARY</p>
          {["YouTube videos", "Instagram Reels", "Recent questions"].map((d, i) => (
            <div key={d} className="flex items-center gap-2 py-1">
              <span className={`h-3 w-3 rounded-full border-2 border-ink ${i === 0 ? "bg-orange" : "bg-sheet"}`} />
              <span className="text-xs font-semibold">{d}</span>
              <span className="ml-auto text-[10px] text-ink-muted">Stored</span>
            </div>
          ))}
        </div>
      </motion.div>
    </div>
  );
}

export function MiniGraph({ className = "h-32 w-full" }: { className?: string }) {
  const n: [number, number][] = [[50, 50], [20, 25], [80, 22], [15, 75], [82, 78], [50, 12], [55, 88], [32, 50], [70, 52]];
  const e: [number, number][] = [[0, 1], [0, 2], [0, 3], [0, 4], [1, 5], [2, 5], [3, 6], [4, 6], [0, 7], [0, 8], [7, 1], [8, 4]];
  return (
    <svg viewBox="0 0 100 100" className={className}>
      {e.map(([a, b], i) => {
        const from = n[a];
        const to = n[b];
        if (!from || !to) return null;
        return <motion.line key={i} x1={from[0]} y1={from[1]} x2={to[0]} y2={to[1]} stroke="var(--ink)" strokeWidth="0.8" initial={{ pathLength: 0, opacity: 0 }} whileInView={{ pathLength: 1, opacity: 1 }} viewport={{ once: true }} transition={{ delay: i * 0.025, duration: 0.45 }} />;
      })}
      {n.map(([x, y], i) => (
        <motion.circle key={i} cx={x} cy={y} r={i === 0 ? 7 : 4} fill={i === 0 || i === 4 ? "var(--orange)" : "var(--sheet)"} stroke="var(--ink)" strokeWidth="1.2" initial={{ scale: 0 }} whileInView={{ scale: 1 }} viewport={{ once: true }} transition={{ delay: 0.2 + i * 0.04, type: "spring" }} style={{ transformOrigin: `${x}px ${y}px` }} />
      ))}
    </svg>
  );
}
