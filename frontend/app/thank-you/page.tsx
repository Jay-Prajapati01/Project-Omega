import type { Metadata } from "next";
import Link from "next/link";
import { ContactConversion } from "@/components/ContactConversion";

export const metadata: Metadata = { title: "Message received | MindMesh", description: "Your MindMesh contact message was received.", robots: { index: false, follow: false } };

export default function ThankYouPage() {
  return <main className="paper-grain grid min-h-screen place-items-center bg-paper px-4 text-ink"><ContactConversion /><div className="brut max-w-xl rounded-3xl bg-paper-card p-8 text-center sm:p-12"><p className="font-mono text-xs font-bold uppercase tracking-widest text-orange">Contact · complete</p><h1 className="mt-4 font-display text-5xl uppercase">Message received.</h1><p className="mt-4 text-ink-muted">Thanks for reaching out. The MindMesh team will review your message.</p><Link href="/" className="brut-btn mt-7 inline-block rounded-xl bg-orange px-5 py-3 font-bold">Back to MindMesh</Link></div></main>;
}
