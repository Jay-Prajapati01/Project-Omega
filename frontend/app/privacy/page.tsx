import type { Metadata } from "next";
import Link from "next/link";
import { Footer, Navbar } from "@/components/landing/Sections";

const business = process.env.NEXT_PUBLIC_PRIVACY_BUSINESS_NAME?.trim() || "[BUSINESS LEGAL NAME — REQUIRED BEFORE LAUNCH]";
const email = process.env.NEXT_PUBLIC_PRIVACY_CONTACT_EMAIL?.trim() || "[PRIVACY CONTACT EMAIL — REQUIRED BEFORE LAUNCH]";

export const metadata: Metadata = {
  title: "MindMesh Privacy Notice | Draft for review",
  description: "Draft privacy notice describing MindMesh data collection and service providers; business details and practices require owner review before launch.",
  robots: { index: true, follow: true },
  openGraph: { title: "MindMesh Privacy Notice", description: "Draft privacy notice for MindMesh.", images: ["/share-card.png"] },
  twitter: { card: "summary_large_image", title: "MindMesh Privacy Notice", description: "Draft privacy notice for MindMesh.", images: ["/share-card.png"] },
};

export default function PrivacyPage() {
  return <div className="paper-grain flex min-h-screen flex-col bg-paper text-ink"><Navbar /><main className="mx-auto w-full max-w-4xl flex-1 px-4 py-14 sm:px-6 sm:py-20"><p className="font-mono text-xs font-bold uppercase tracking-widest text-orange">Draft · owner and legal review required</p><h1 className="mt-4 font-display text-6xl uppercase sm:text-8xl">Privacy <span className="text-orange">notice.</span></h1><p className="mt-5 text-sm text-ink-muted">Last updated: October 14, 2026. This draft contains placeholders and describes integrations visible in the current application. It is not ready to publish until the operator confirms the actual practices, retention periods, jurisdictions, and legal requirements.</p>
    <div className="mt-9 space-y-8 leading-relaxed"><section><h2 className="font-display text-2xl uppercase">Who operates MindMesh</h2><p className="mt-2">Operator: <strong>{business}</strong>. Privacy contact: <strong>{email}</strong>. Replace these placeholders with the responsible legal entity and monitored email before launch.</p></section>
    <section><h2 className="font-display text-2xl uppercase">Information the app may process</h2><p className="mt-2">Account details supplied during sign-up, saved source URLs and extracted content, conversations and AI requests, contact-form details, usage and processing status, and technical request information may be processed to provide the service. Confirm the exact fields, logs, retention periods, and deletion process before publication.</p></section>
    <section><h2 className="font-display text-2xl uppercase">Storage and service providers</h2><p className="mt-2">The current codebase integrates with Supabase for authentication and cloud data; Qdrant for vector search; configured AI providers for model requests; and optional Razorpay for payments. YouTube and Instagram content may be fetched from public links. Which providers are active, their legal entities, regions, and retention terms depend on deployment configuration and must be verified by the operator.</p></section>
    <section><h2 className="font-display text-2xl uppercase">Optional anonymous analytics</h2><p className="mt-2">MindMesh asks visitors before enabling first-party analytics. If accepted, it stores a random browser identifier and coarse allowlisted page and feature events to count unique browsers, visits, and recently active browsers. It does not include account names, chat prompts, saved-source URLs, or IP addresses in analytics events. Visitors can decline or change their choice through Cookie settings. The operator should verify database retention and applicable legal requirements before launch. If configured, Google Analytics is also loaded only after consent.</p></section>
    <section><h2 className="font-display text-2xl uppercase">Cookies and local storage</h2><p className="mt-2">The app uses browser storage for essential application preferences and authentication state. Analytics consent and the random analytics browser identifier are stored locally in the browser. Confirm storage lifetimes and deletion/retention procedures before launch.</p></section>
    <section><h2 className="font-display text-2xl uppercase">Your choices and requests</h2><p className="mt-2">Contact the operator at {email} for privacy questions or requests. The operator must add the applicable process for access, correction, deletion, withdrawal, complaints, and response times for the jurisdictions served.</p></section>
    <section><h2 className="font-display text-2xl uppercase">Changes and unresolved details</h2><p className="mt-2">Before launch, confirm legal basis, purposes, data retention, international transfers, children’s access, security practices, subprocessors, and jurisdiction-specific disclosures with qualified counsel. Do not treat this draft as legal advice.</p></section></div>
    <div className="mt-10 flex flex-wrap gap-4"><Link className="font-bold text-orange underline" href="/faq">Read the FAQ</Link><Link className="font-bold text-orange underline" href="/contact">Contact</Link></div></main><Footer /></div>;
}
