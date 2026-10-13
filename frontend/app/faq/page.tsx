import type { Metadata } from "next";
import Link from "next/link";
import { Footer, Navbar } from "@/components/landing/Sections";

export const metadata: Metadata = {
  title: "MindMesh FAQ | Getting started and saved sources",
  description: "Draft answers about MindMesh accounts, saved links, AI answers, privacy, and plans. Please review before launch.",
  robots: { index: true, follow: true },
  openGraph: { title: "MindMesh FAQ", description: "Answers about saving sources and using MindMesh.", images: ["/share-card.png"] },
  twitter: { card: "summary_large_image", title: "MindMesh FAQ", description: "Answers about saving sources and using MindMesh.", images: ["/share-card.png"] },
};

const faqs = [
  ["What is MindMesh?", "MindMesh is a personal knowledge workspace for saving supported YouTube and Instagram links, organizing the resulting sources, and asking questions about saved material."],
  ["What can I save?", "The current product is designed for YouTube videos and Shorts, plus public Instagram Reels and posts. Available transcript, caption, and source details depend on the original content and platform access."],
  ["How does Ask AI work?", "Ask AI answers questions using sources in your MindMesh library and can show source references. Results can be incomplete or incorrect, so check important details against the cited material."],
  ["Do I need an account?", "Yes. Sign in or create an account to use your personal workspace and keep saved sources associated with your account."],
  ["Are my saved sources public?", "The product presents a private workspace tied to your account. Review the Privacy Notice for the services and data handling that still need to be confirmed before launch."],
  ["Is public pricing available?", "MindMesh is launching without a public pricing page. Current usage limits remain visible in your account."],
  ["What if a link does not process?", "Some content may be unavailable, private, restricted, or missing accessible captions. Check the source status in your workspace, then contact support with the link and error details."],
  ["How can I contact the team or request help?", "Use the Contact form to send a support or general question. Do not include passwords, payment card details, or other sensitive information in a message."],
];

export default function FAQPage() {
  return <div className="paper-grain flex min-h-screen flex-col bg-paper text-ink"><Navbar /><main className="mx-auto w-full max-w-4xl flex-1 px-4 py-14 sm:px-6 sm:py-20"><p className="font-mono text-xs font-bold uppercase tracking-widest text-orange">Draft FAQ · review before launch</p><h1 className="mt-4 font-display text-6xl uppercase sm:text-8xl">Questions, <span className="text-orange">answered.</span></h1><p className="mt-5 max-w-2xl text-ink-muted">These draft answers describe the current app. Please confirm them against your final product and policies before launch.</p><div className="mt-10 grid gap-4">{faqs.map(([q, a]) => <details key={q} className="brut rounded-2xl bg-paper-card p-5"><summary className="cursor-pointer text-lg font-extrabold">{q}</summary><p className="mt-3 leading-relaxed text-ink-muted">{a}</p></details>)}</div><p className="mt-8">Still have a question? <Link className="font-bold text-orange underline" href="/contact">Contact the team</Link>.</p></main><Footer /></div>;
}
