import { motion, useMotionValue, useScroll, useSpring, useTransform, type MotionValue } from "motion/react";
import { useRef, type MouseEvent } from "react";
import { Youtube, Instagram, MessageSquare, Bookmark, type LucideIcon } from "lucide-react";
import { Label } from "./ui";

type F = { icon: LucideIcon; title: string; desc: string; tags: string[]; preview: string[] };
const FEATURES: F[] = [
  { icon: Youtube, title: "YouTube Intelligence", desc: "Save a video or Short and ask questions about its transcript and key moments.", tags: ["Videos", "Shorts", "Transcripts"], preview: ["Video saved", "Transcript indexed", "00:41 Key idea", "Ready for Ask AI"] },
  { icon: Instagram, title: "Instagram Intelligence", desc: "Save public posts and Reels with captions and visible frame text in your library.", tags: ["Posts", "Reels", "Captions"], preview: ["Reel saved", "Caption captured", "Frame text indexed", "Ready for Ask AI"] },
  { icon: MessageSquare, title: "Ask AI", desc: "Ask natural-language questions across your saved YouTube and Instagram sources.", tags: ["Ask", "Search", "Citations"], preview: ["Question understood", "Relevant sources found", "Answer grounded", "Open source citation"] },
  { icon: Bookmark, title: "Stored", desc: "Keep your saved links, processing status, and source details together by account.", tags: ["Your library", "Search", "Source status"], preview: ["YouTube videos", "Instagram Reels", "Processing status", "Private to your workspace"] },
];

export function Features() {
  const ref = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start start", "end end"] });
  return (
    <section id="features" className="scroll-mt-24 px-4 py-28">
      <div className="mx-auto max-w-6xl">
        <div className="mb-16 flex flex-col items-start gap-4">
          <Label>Features</Label>
          <h2 className="font-display uppercase leading-[0.9] text-[clamp(3rem,7vw,6.5rem)]">
            One Brain. <span className="text-orange">Four Features.</span>
          </h2>
        </div>
        <div ref={ref} className="flex flex-col gap-8 md:gap-[30vh]">
          {FEATURES.map((f, i) => (
            <Card key={f.title} f={f} i={i} n={FEATURES.length} p={scrollYProgress} />
          ))}
        </div>
      </div>
    </section>
  );
}

function Card({ f, i, n, p }: { f: F; i: number; n: number; p: MotionValue<number> }) {
  const last = i === n - 1;
  const a = i / n, b = (i + 1) / n;
  const scale = useTransform(p, [a, b], [1, last ? 1 : 0.94]);
  const rotate = useTransform(p, [a, b], [0, last ? 0 : -2]);
  const shade = useTransform(p, [a, b], [0, last ? 0 : 0.18]);
  const rx = useMotionValue(0), ry = useMotionValue(0);
  const srx = useSpring(rx, { stiffness: 120, damping: 20 });
  const sry = useSpring(ry, { stiffness: 120, damping: 20 });
  const onMove = (e: MouseEvent<HTMLDivElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    ry.set(((e.clientX - r.left) / r.width - 0.5) * 12);
    rx.set(-((e.clientY - r.top) / r.height - 0.5) * 12);
  };
  const I = f.icon;
  return (
    <div className="md:sticky" style={{ top: 120 + i * 14 }}>
      <motion.div
        style={{ scale, rotate }}
        initial={{ y: 60, opacity: 0 }}
        whileInView={{ y: 0, opacity: 1 }}
        viewport={{ once: true }}
        transition={{ type: "spring", stiffness: 120, damping: 20 }}
        className="origin-top [perspective:1200px]"
      >
        <motion.div
          onMouseMove={onMove}
          onMouseLeave={() => { rx.set(0); ry.set(0); }}
          style={{ rotateX: srx, rotateY: sry }}
          className={`brut relative grid gap-8 overflow-hidden p-7 md:grid-cols-2 md:p-10 ${i % 2 ? "bg-paper-card" : "bg-sheet"}`}
        >
          <motion.div style={{ opacity: shade }} className="pointer-events-none absolute inset-0 bg-ink" />
          <div className="flex flex-col">
            <div className="flex items-center gap-3">
              <span className="grid h-12 w-12 place-items-center rounded-xl border-2 border-ink bg-orange"><I className="h-6 w-6" /></span>
              <span className="font-mono text-xs font-bold text-ink-muted">0{i + 1} / 0{n}</span>
            </div>
            <h3 className="mt-6 text-[32px] font-extrabold leading-tight tracking-tight">{f.title}</h3>
            <p className="mt-2 text-lg text-ink-muted">{f.desc}</p>
            <div className="mt-auto flex flex-wrap gap-2 pt-6">
              {f.tags.map((t) => (
                <span key={t} className="rounded-full border-2 border-ink bg-paper px-3 py-1 font-mono text-xs font-bold uppercase">{t}</span>
              ))}
            </div>
          </div>
          <div className="rounded-2xl border-2 border-ink bg-paper p-5">
            <div className="mb-4 flex items-center justify-between">
              <span className="font-mono text-[10px] font-bold tracking-widest text-ink-muted">PREVIEW</span>
              <span className="rounded-full border-2 border-ink bg-orange px-2 font-mono text-[10px] font-bold">LIVE</span>
            </div>
            {f.preview.map((l, k) => (
              <div key={l} className="mb-2 flex items-center gap-3 rounded-xl border-2 border-ink bg-sheet px-3 py-2.5">
                <span className={`h-2.5 w-2.5 rounded-full border-2 border-ink ${k === f.preview.length - 1 ? "bg-orange" : "bg-paper-card"}`} />
                <span className="font-mono text-sm font-bold">{l}</span>
              </div>
            ))}
          </div>
        </motion.div>
      </motion.div>
    </div>
  );
}
