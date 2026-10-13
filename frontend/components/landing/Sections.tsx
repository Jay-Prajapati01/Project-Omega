"use client";

import { motion, useScroll, useSpring } from "motion/react";
import { lazy, Suspense, useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { usePathname, useRouter } from "next/navigation";
import { ArrowRight, MessageSquare, Instagram, Youtube, Bookmark, Unlink, BrainCircuit, Zap, MoveRight, type LucideIcon } from "lucide-react";
import { Btn, FadeUp, Label } from "./ui";
import { ThemeToggle } from "./ThemeToggle";
import { useAuth } from "../CloudAuthGate";

function useIdentity() {
  const { session } = useAuth();
  const meta = (session?.user.user_metadata ?? {}) as Record<string, unknown>;
  const displayName =
    (typeof meta.preferred_name === "string" && meta.preferred_name.trim()) ||
    (typeof meta.full_name === "string" && meta.full_name.trim()) ||
    session?.user.email?.split("@")[0] ||
    "Your profile";
  const initials =
    displayName.trim().split(/\s+/).filter(Boolean).slice(0, 2).map((p) => p[0]).join("").toUpperCase() || "M";
  return { session, displayName: displayName.trim(), initials };
}

export function Marquee() {
  const t = "YOUTUBE • INSTAGRAM • ASK AI • STORED • YOUTUBE • INSTAGRAM • ASK AI • STORED • ";
  return (
    <div className="overflow-hidden border-y-2 border-ink bg-orange">
      <div className="overflow-hidden border-b-2 border-ink py-2.5 md:py-3">
        <div className="animate-marquee flex w-max items-center whitespace-nowrap">
          {[0, 1, 2, 3].map((k) => (
            <span key={k} className="font-display pr-10 text-2xl uppercase leading-none text-ink md:text-3xl">{t}</span>
          ))}
        </div>
      </div>
      <div className="overflow-hidden bg-paper-card py-2.5 md:py-3">
        <div className="animate-marquee-reverse flex w-max items-center whitespace-nowrap">
          {[0, 1, 2, 3].map((k) => (
            <span key={k} className="font-display pr-10 text-2xl uppercase leading-none text-ink md:text-3xl">{t}</span>
          ))}
        </div>
      </div>
    </div>
  );
}

export function ProblemSolution() {
  const cards = [
    { n: "01", tag: "CHAOS", icon: Unlink, t: "The Problem", d: "Useful ideas disappear into YouTube watch history, Instagram Reels, and a pile of open tabs.", bg: "bg-sheet", iconBg: "bg-paper-card" },
    { n: "02", tag: "MINDMESH", icon: BrainCircuit, t: "The MindMesh Way", d: "Save YouTube and Instagram links, then ask AI questions grounded in the sources you stored.", bg: "bg-orange", iconBg: "bg-sheet" },
    { n: "03", tag: "CLARITY", icon: Zap, t: "The Result", d: "A searchable private library that keeps your saved sources, answers, and processing status together.", bg: "bg-paper-card", iconBg: "bg-orange" },
  ];
  return (
    <section className="px-4 pb-10 pt-20 sm:pb-14 sm:pt-24">
      <div className="mx-auto mb-10 grid max-w-6xl grid-cols-[minmax(0,1fr)_auto] items-end gap-4">
        <div className="min-w-0">
          <Label>From noise to knowledge</Label>
          <h2 className="font-display mt-4 max-w-4xl uppercase leading-[0.92] text-[clamp(2.8rem,6vw,5.7rem)]">One flow. <span className="text-orange">Zero hunting.</span></h2>
        </div>
        <MoveRight className="hidden h-12 w-12 shrink-0 text-orange sm:block" strokeWidth={2.5} />
      </div>
      <div className="mx-auto grid max-w-6xl gap-5 md:grid-cols-3">
        {cards.map((c, i) => (
          <FadeUp key={c.t} delay={i * 0.1}>
            <motion.article
              whileHover={{ y: -8, rotate: i === 0 ? -1 : i === 2 ? 1 : 0 }}
              transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
              className={`process-card brut relative flex min-h-[330px] h-full flex-col overflow-hidden p-6 sm:p-7 ${c.bg}`}
            >
              <div className="absolute -right-3 -top-7 font-display text-[8rem] leading-none text-ink/10" aria-hidden="true">{c.n}</div>
              <div className="relative flex items-start justify-between gap-4">
                <span className={`grid h-16 w-16 shrink-0 place-items-center rounded-2xl border-2 border-ink shadow-[3px_3px_0_var(--ink)] ${c.iconBg}`}>
                  <c.icon className="h-8 w-8" strokeWidth={2.4} />
                </span>
                <span className="rounded-full border-2 border-ink bg-paper px-3 py-1 font-mono text-[10px] font-bold tracking-widest">{c.tag}</span>
              </div>
              <div className="relative mt-auto pt-12">
                <span className="font-mono text-xs font-bold text-ink-muted">STEP / {c.n}</span>
                <h3 className="mt-2 text-2xl font-extrabold sm:text-3xl">{c.t}</h3>
                <p className="mt-3 text-[15px] leading-relaxed text-ink">{c.d}</p>
              </div>
              <div className="absolute bottom-0 left-0 h-2 w-full border-t-2 border-ink bg-orange" />
            </motion.article>
          </FadeUp>
        ))}
      </div>
    </section>
  );
}

export function HowItWorks() {
  const ref = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start 80%", "end 50%"] });
  const fill = useSpring(scrollYProgress, { stiffness: 100, damping: 30 });
  const steps = [
    ["01", "CAPTURE", "Share a YouTube or Instagram link."],
    ["02", "UNDERSTAND", "Extract its transcript, caption, and available content."],
    ["03", "STORE", "Keep the source in your private library."],
    ["04", "ASK", "Get an answer grounded in your saved sources."],
  ];
  return (
    <section id="how" className="scroll-mt-24 border-y-2 border-ink bg-paper-alt px-4 py-28">
      <div className="mx-auto max-w-6xl">
        <Label>How it works</Label>
        <h2 className="font-display mt-4 uppercase leading-[0.9] text-[clamp(3rem,7vw,6.5rem)]">
          Four steps to <span className="text-orange">total recall.</span>
        </h2>
        <div ref={ref} className="relative mt-16">
          <div className="absolute left-0 right-0 top-8 hidden h-[6px] rounded-full border-2 border-ink bg-sheet md:block">
            <motion.div style={{ scaleX: fill }} className="h-full origin-left rounded-full bg-orange" />
          </div>
          <div className="grid gap-8 md:grid-cols-4">
            {steps.map(([n, t, d]) => (
              <div key={n} className="relative">
                <span className="brut font-display relative z-10 grid h-16 w-16 place-items-center rounded-2xl bg-orange text-2xl">{n}</span>
                <h3 className="font-display mt-6 text-3xl uppercase">{t}</h3>
                <p className="mt-2 text-ink-muted">{d}</p>
              </div>
            ))}
          </div>
        </div>
        <FadeUp className="mt-16">
          <div className="brut flex flex-col items-start justify-between gap-4 bg-ink p-5 md:flex-row md:items-center md:p-6">
            <div><p className="font-mono text-xs font-bold uppercase tracking-widest text-orange">Ready when you are</p><p className="mt-1 text-lg font-bold text-paper md:text-xl">Create your account and start building your personal knowledge workspace.</p></div>
            <Link href="/signup" className="brut-btn shrink-0 bg-orange px-4 py-2 text-sm font-bold">Create account <ArrowRight className="inline h-4 w-4" /></Link>
          </div>
        </FadeUp>
      </div>
    </section>
  );
}

export function Bento() {
  return (
    <section id="ask-ai" className="scroll-mt-24 px-4 py-28">
      <div className="mx-auto max-w-6xl">
        <Label>Showcase</Label>
        <h2 className="font-display mt-4 mb-14 uppercase leading-[0.9] text-[clamp(3rem,7vw,6.5rem)]">
          Built like a <span className="text-orange">real OS.</span>
        </h2>
        <div className="grid auto-rows-[260px] gap-6 md:grid-cols-3">
          <FadeUp className="md:col-span-2 md:row-span-2">
            <Tile icon={MessageSquare} title="Ask AI" desc="Get answers grounded in your saved YouTube and Instagram sources." className="bg-sheet">
              <div className="mt-4 space-y-3">
                <div className="ml-auto w-fit rounded-2xl border-2 border-ink bg-paper-card px-4 py-2 font-semibold">What should I remember from this Reel?</div>
                <div className="max-w-md rounded-2xl border-2 border-ink bg-paper p-4">
                  The Reel highlights a simple planning routine <b className="text-orange">[1]</b>. Your saved YouTube video explains how to apply it <b className="text-orange">[2]</b>.
                </div>
                <span className="inline-block rounded-full border-2 border-ink bg-orange px-3 py-1 font-mono text-xs font-bold">SOURCES · 2</span>
              </div>
            </Tile>
          </FadeUp>
          <FadeUp delay={0.1}><Tile icon={Youtube} title="YouTube" desc="Save videos and Shorts with searchable transcripts." className="bg-paper-card"><p className="mt-4 font-mono text-xs font-bold">TRANSCRIPT · CHAPTERS · CITATIONS</p></Tile></FadeUp>
          <FadeUp delay={0.2}><Tile icon={Instagram} title="Instagram" desc="Keep public Reels and posts with their captions." className="bg-orange"><p className="mt-4 font-mono text-xs font-bold">REELS · POSTS · CAPTIONS</p></Tile></FadeUp>
          <FadeUp delay={0.3}><Tile icon={Bookmark} title="Stored" desc="Find your saved links and see their processing status." className="bg-paper-card"><p className="mt-4 font-mono text-xs font-bold">PRIVATE · SEARCHABLE · ORGANIZED</p></Tile></FadeUp>
        </div>
      </div>
    </section>
  );
}

function Tile({ icon: I, title, desc, className, children }: { icon: LucideIcon; title: string; desc: string; className: string; children?: React.ReactNode }) {
  return (
    <div className={`brut lift flex h-full flex-col overflow-hidden p-6 ${className}`}>
      <div className="flex items-center gap-3">
        <span className="grid h-10 w-10 place-items-center rounded-xl border-2 border-ink bg-sheet"><I className="h-5 w-5" /></span>
        <div><h3 className="text-lg font-extrabold leading-tight">{title}</h3><p className="text-sm text-ink-muted">{desc}</p></div>
      </div>
      {children}
    </div>
  );
}

export function Stats() {
  const rows = [
    ["01", "Your Workspace", "Your sources and conversations stay with your account."],
    ["02", "Connected Ideas", "Find connections across the knowledge you save."],
    ["03", "Grounded Answers", "Ask questions and follow citations back to your sources."],
  ];
  return (
    <section id="your-workspace" className="scroll-mt-24 px-4 py-28">
      <div className="mx-auto max-w-6xl border-b-2 border-ink">
        {rows.map(([n, t, d]) => (
          <div key={t} className="group relative overflow-hidden border-t-2 border-ink">
            <div className="absolute inset-0 origin-bottom scale-y-0 bg-orange transition-transform duration-500 [transition-timing-function:var(--ease-brut)] group-hover:scale-y-100" />
            <div className="relative flex flex-col gap-2 py-8 md:flex-row md:items-center md:gap-10">
              <span className="font-display text-orange text-[clamp(3.5rem,8vw,7rem)] leading-none transition-colors group-hover:text-ink">{n}</span>
              <span className="font-display text-[clamp(2rem,5vw,4.5rem)] uppercase leading-none">{t}</span>
              <span className="max-w-xs text-base font-semibold md:ml-auto md:text-right">{d}</span>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

export function CustomerStories() {
  return (
    <section className="border-y-2 border-ink bg-paper-alt px-4 py-16">
      <div className="mx-auto max-w-6xl">
        <Label>Customer stories</Label>
        <div className="brut mt-5 rounded-3xl bg-paper-card p-6 sm:p-9">
          <h2 className="font-display text-3xl uppercase sm:text-4xl">Real stories belong here.</h2>
          <p className="mt-3 max-w-2xl text-ink-muted">We are collecting feedback from real MindMesh users. Testimonials will appear here only after the authors approve their words and attribution.</p>
          <p className="mt-5 inline-flex rounded-full border-2 border-ink bg-orange px-3 py-1 font-mono text-xs font-bold uppercase tracking-widest">No customer reviews published yet</p>
        </div>
      </div>
    </section>
  );
}

export function FinalCTA() {
  return (
    <section className="border-t-2 border-ink bg-paper-alt px-4 py-32 text-center">
      <FadeUp>
        <h2 className="font-display mx-auto max-w-5xl uppercase leading-[0.9] tracking-[-0.03em] text-[clamp(3.5rem,9vw,8.5rem)]">
          Stop searching. <span className="text-orange text-stroke">Start asking.</span>
        </h2>
        <div className="mt-10"><Btn href="/signup">Create Your Account <ArrowRight className="h-4 w-4" /></Btn></div>
        <p className="mt-6 font-mono text-sm font-bold text-ink-muted">Your sources. Your ideas. One personal workspace.</p>
      </FadeUp>
    </section>
  );
}

export function Footer() {
  const { session } = useAuth();
  return (
    <footer className="border-t-2 border-ink px-4 py-8">
      <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 md:flex-row">
        <Logo />
        <div className="flex items-center gap-6 text-sm font-bold">
          {session ? (
            <Link href="/profile" className="hover:text-orange">Profile</Link>
          ) : (
            <Link href="/login" className="hover:text-orange">Sign in</Link>
          )}
          <Link href="/contact" className="hover:text-orange">Contact</Link>
          <Link href="/faq" className="hover:text-orange">FAQ</Link>
          <Link href="/privacy" className="hover:text-orange">Privacy</Link>
          <button type="button" onClick={() => window.dispatchEvent(new Event("mindmesh:open-cookie-settings"))} className="hover:text-orange">Cookie settings</button>
          <span className="text-ink-muted">© {new Date().getFullYear()} MindMesh</span>
        </div>
      </div>
    </footer>
  );
}

export function Logo() {
  return (
    <Link href="/" className="flex min-w-0 items-center gap-2">
      <span className="grid h-9 w-9 place-items-center overflow-hidden rounded-lg bg-[#111]">
        <Image src="/logo.png" alt="" width={36} height={36} className="h-full w-full object-contain p-1" />
      </span>
      <span className="truncate text-lg font-extrabold tracking-tight sm:text-xl">MindMesh</span>
    </Link>
  );
}

export function Navbar() {
  const { session, displayName, initials } = useIdentity();
  return (
    <header className="sticky top-0 z-50 h-16 border-b-2 border-ink bg-paper/80 backdrop-blur-md">
      <div className="mx-auto flex h-full max-w-7xl items-center justify-between gap-2 px-3 sm:gap-4 sm:px-4">
        <Logo />
        <nav className="hidden items-center gap-8 text-sm font-bold lg:flex">
          {[["Features", "/#features"], ["How it works", "/#how"], ["Ask AI", "/#ask-ai"], ["Your Workspace", "/#your-workspace"]].map(([l, h]) => (
            <a key={l} href={h} className="hover:text-orange">{l}</a>
          ))}
        </nav>
        <div className="flex shrink-0 items-center gap-1.5 sm:gap-3">
          <ThemeToggle />
          {session ? (
            <>
              <Link href="/dashboard" className="hidden text-sm font-bold hover:text-orange sm:block">Open workspace</Link>
              <Link
                href="/profile"
                title="Your profile"
                className="brut-btn flex items-center gap-2 rounded-xl bg-paper px-2.5 py-1.5 text-sm font-bold"
              >
                <span className="grid h-6 w-6 shrink-0 place-items-center rounded-lg border-2 border-ink bg-orange text-[10px] font-extrabold">{initials}</span>
                <span className="hidden max-w-36 truncate sm:inline">{displayName}</span>
              </Link>
            </>
          ) : (
            <>
              <Link href="/login" className="hidden text-sm font-bold hover:text-orange min-[420px]:block">Sign in</Link>
              <Link href="/signup" className="brut-btn rounded-xl bg-orange px-2.5 py-2 text-xs font-bold hover:bg-orange-hover sm:px-3 sm:text-sm">Get Started</Link>
            </>
          )}
          <ContactWithPass />
        </div>
      </div>
    </header>
  );
}

const LanyardPass = lazy(() => import("./LanyardPass"));

function ContactWithPass() {
  const [show, setShow] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(min-width: 768px) and (prefers-reduced-motion: no-preference)");
    const u = () => setShow(mq.matches);
    u(); mq.addEventListener("change", u);
    return () => mq.removeEventListener("change", u);
  }, []);
  const router = useRouter();
  const pathname = usePathname();
  const onContact = pathname === "/contact";
  const contact = useCallback(() => { router.push("/contact"); }, [router]);
  return (
    <div className="relative">
      <Link href="/contact" className="brut-btn relative z-10 flex items-center rounded-xl bg-paper px-2.5 py-2 text-xs font-bold sm:px-3 sm:text-sm">Contact</Link>
      {show && !onContact && <Suspense fallback={null}><LanyardPass onTap={contact} /></Suspense>}
    </div>
  );
}
