"use client";

import { useEffect, useRef } from "react";
import Lenis from "lenis";
import { IntroReveal } from "./IntroReveal";
import { Hero } from "./Hero";
import { Manifesto } from "./Manifesto";
import { Features } from "./Features";
import { Navbar, Marquee, ProblemSolution, HowItWorks, Bento, Stats, CustomerStories, FinalCTA, Footer } from "./Sections";

const NAV_OFFSET = 72; // sticky navbar height + breathing room

export function LandingPage() {
  const lenisRef = useRef<Lenis | null>(null);

  useEffect(() => {
    const lenis = new Lenis({ lerp: 0.1 });
    lenisRef.current = lenis;
    let id = 0;
    const raf = (t: number) => { lenis.raf(t); id = requestAnimationFrame(raf); };
    id = requestAnimationFrame(raf);
    let t = 0;
    const onHold = (e: Event) => {
      lenis.stop();
      const html = document.documentElement;
      html.style.overflow = "hidden";
      clearTimeout(t);
      t = window.setTimeout(() => { html.style.overflow = ""; lenis.start(); }, (e as CustomEvent<number>).detail ?? 2000);
    };
    window.addEventListener("mindmesh:intro-hold", onHold);
    return () => { cancelAnimationFrame(id); clearTimeout(t); window.removeEventListener("mindmesh:intro-hold", onHold); document.documentElement.style.overflow = ""; lenis.destroy(); lenisRef.current = null; };
  }, []);

  // Deep links (e.g. /#features clicked from /contact) must land on the right
  // section after hydration — the intro spacer changes document offsets, so a
  // one-shot post-mount scroll keeps the anchor accurate.
  useEffect(() => {
    const id = decodeURIComponent(window.location.hash.replace(/^#/, ""));
    if (!id) return;
    const timer = window.setTimeout(() => {
      const el = document.getElementById(id);
      if (!el) return;
      const lenis = lenisRef.current;
      if (lenis) lenis.scrollTo(el, { immediate: true, offset: -NAV_OFFSET });
      else window.scrollTo({ top: el.getBoundingClientRect().top + window.scrollY - NAV_OFFSET });
    }, 250);
    return () => window.clearTimeout(timer);
  }, []);

  return (
    <div className="paper-grain min-h-screen overflow-x-clip text-ink">
      <IntroReveal>
        <Navbar />
        <main>
          <Hero />
          <Marquee />
          <Manifesto />
          <ProblemSolution />
          <Features />
          <HowItWorks />
          <Bento />
          <Stats />
          <CustomerStories />
          <FinalCTA />
        </main>
        <Footer />
      </IntroReveal>
    </div>
  );
}
