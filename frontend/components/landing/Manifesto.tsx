import { motion, useScroll, useTransform, useSpring, type MotionValue } from "motion/react";
import { useRef } from "react";
import { FileText, Play } from "lucide-react";
import { Label } from "./ui";

type Tok = { w: string; orange?: boolean; pill?: "yt" | "pdf" | "audio" };
const TOKENS: Tok[] = [
  { w: "EVERYTHING" }, { w: "YOU" }, { w: "WATCH,", pill: "yt" }, { w: "READ,", pill: "pdf" },
  { w: "HEAR", pill: "audio" }, { w: "AND" }, { w: "SAVE," }, { w: "UNIFIED" },
  { w: "INTO" }, { w: "ONE", orange: true }, { w: "BRAIN", orange: true }, { w: "YOU" },
  { w: "CAN" }, { w: "TALK" }, { w: "TO." },
];

export function Manifesto() {
  const ref = useRef<HTMLElement>(null);
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start 90%", "start 25%"] });
  const p = useSpring(scrollYProgress, { stiffness: 120, damping: 30, restDelta: 0.001 });
  const n = TOKENS.length;
  return (
    <section ref={ref} className="manifesto-scroll relative bg-paper-alt md:h-[95dvh]">
      <div className="flex flex-col items-center gap-5 px-6 pb-10 pt-10 md:sticky md:top-16 md:pb-10 md:pt-10">
        <Label>Manifesto</Label>
        <p className="font-display max-w-6xl text-center uppercase leading-[1.02] text-[clamp(2.2rem,6vw,5.6rem)]">
          {TOKENS.map((t, i) => (
            <Word key={i} t={t} p={p} start={(i / n) * 0.85} end={((i + 1) / n) * 0.85} />
          ))}
        </p>
      </div>
    </section>
  );
}

function Word({ t, p, start, end }: { t: Tok; p: MotionValue<number>; start: number; end: number }) {
  const opacity = useTransform(p, [start, end], [0.15, 1]);
  const pillW = useTransform(p, [start, end], [0, 120]);
  return (
    <>
      <motion.span style={{ opacity }} className={`mr-[0.25em] inline-block ${t.orange ? "text-orange" : ""}`}>
        {t.w}
      </motion.span>
      {t.pill && (
        <motion.span
          style={{ width: pillW }}
          className="mr-[0.25em] inline-flex h-[0.8em] translate-y-[-0.05em] items-center justify-center overflow-hidden rounded-full border-2 border-ink align-middle"
        >
          <Pill kind={t.pill} />
        </motion.span>
      )}
    </>
  );
}

function Pill({ kind }: { kind: "yt" | "pdf" | "audio" }) {
  if (kind === "yt")
    return (
      <span className="grid h-full w-[120px] shrink-0 place-items-center bg-ink">
        <span className="grid h-7 w-10 place-items-center rounded-lg bg-orange"><Play className="h-4 w-4 fill-ink" /></span>
      </span>
    );
  if (kind === "pdf")
    return (
      <span className="flex h-full w-[120px] shrink-0 items-center gap-2 bg-sheet px-3">
        <FileText className="h-6 w-6 shrink-0 text-orange" />
        <span className="flex flex-1 flex-col gap-1">
          {[1, 0.7, 0.85].map((w, i) => <span key={i} className="h-1 rounded bg-ink" style={{ width: `${w * 100}%` }} />)}
        </span>
      </span>
    );
  return (
    <span className="flex h-full w-[120px] shrink-0 items-center justify-center gap-[3px] bg-orange">
      {[4, 8, 12, 6, 14, 9, 5, 11, 7, 13, 4, 8].map((h, i) => (
        <span key={i} className="w-[3px] rounded bg-ink" style={{ height: h * 2.4 }} />
      ))}
    </span>
  );
}
