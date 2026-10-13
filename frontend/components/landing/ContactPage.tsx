"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { z } from "zod";
import { ArrowLeft, Check, Send } from "lucide-react";
import { motion } from "motion/react";
import { api } from "@/lib/api";
import { Navbar, Footer } from "./Sections";
import { Label, EASE } from "./ui";

const TOPICS = ["General", "Account support", "Partnership", "Bug / feedback"] as const;

const schema = z.object({
  name: z.string().trim().min(1, "Tell us your name").max(100),
  email: z.string().trim().email("Enter a valid email").max(255),
  company: z.string().trim().max(120).optional(),
  website: z.string().max(200).optional(),
  topic: z.enum(TOPICS),
  message: z.string().trim().min(10, "At least 10 characters").max(2000),
});

const field = "brut w-full rounded-2xl bg-paper px-4 py-3 text-base text-ink outline-none placeholder:text-ink-muted focus:bg-sheet";

export function ContactPage() {
  const router = useRouter();
  const [topic, setTopic] = useState<(typeof TOPICS)[number]>("General");
  const [errors, setErrors] = useState<Partial<Record<string, string>>>({});
  const [state, setState] = useState<"idle" | "sending" | "done" | "error">("idle");

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    const parsed = schema.safeParse({
      name: fd.get("name"), email: fd.get("email"),
      company: (fd.get("company") as string) || undefined, topic, message: fd.get("message"),
      website: fd.get("website") || "",
    });
    if (!parsed.success) {
      const errs: Record<string, string> = {};
      for (const i of parsed.error.issues) errs[String(i.path[0])] = i.message;
      setErrors(errs); return;
    }
    setErrors({}); setState("sending");
    try {
      // Delivered to the MindMesh API (public endpoint — no account needed).
      await api.post("/contact", {
        name: parsed.data.name,
        email: parsed.data.email,
        company: parsed.data.company ?? null,
        topic: parsed.data.topic,
        message: parsed.data.message,
        website: parsed.data.website ?? "",
      });
      router.push("/thank-you?source=contact");
    } catch {
      setState("error");
    }
  }

  return (
    <div className="paper-grain flex min-h-screen flex-col overflow-x-clip bg-paper text-ink">
      <Navbar />
      <main className="mx-auto grid w-full max-w-6xl flex-1 gap-7 px-4 py-8 sm:gap-10 sm:px-6 sm:py-10 md:grid-cols-[1fr_1.15fr] md:py-14">
        <motion.div initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, ease: EASE }}>
          <Link href="/" className="mb-8 flex w-fit items-center gap-2 font-mono text-xs font-bold uppercase tracking-widest"><ArrowLeft className="h-4 w-4" />Back home</Link>
          <Label>Contact</Label>
          <h1 className="mt-5 font-display text-[clamp(3rem,8vw,6.5rem)] uppercase leading-[0.9] tracking-[-0.04em]">
            Let&apos;s talk <span className="text-orange">brains.</span>
          </h1>
          <p className="mt-6 max-w-md text-lg text-ink-muted">Questions about your account, help with MindMesh, or a partnership idea — drop us a line and the team will reply.</p>
          <div className="brut mt-8 rounded-3xl bg-paper-card p-4 sm:p-6">
            <p className="font-mono text-xs font-bold uppercase tracking-widest text-ink-muted">[ Here to help ]</p>
            <p className="mt-2 font-display text-2xl uppercase">Your knowledge, connected</p>
          </div>
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 32 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, ease: EASE, delay: 0.1 }}
          className="brut rounded-3xl bg-paper-card p-4 sm:p-6 md:p-8">
          {state === "done" ? (
            <div className="flex min-h-[420px] flex-col items-start justify-center gap-5">
              <span className="brut grid h-16 w-16 place-items-center rounded-2xl bg-orange"><Check className="h-8 w-8" /></span>
              <h2 className="font-display text-4xl uppercase">Message received.</h2>
              <p className="text-ink-muted">Thanks for reaching out — we&apos;ll get back to you soon.</p>
              <Link href="/" className="brut-btn rounded-2xl bg-paper px-5 py-3 font-bold">Back to MindMesh</Link>
            </div>
          ) : (
            <form onSubmit={submit} noValidate className="grid gap-5">
              <div aria-hidden="true" className="absolute -left-[10000px] top-auto h-px w-px overflow-hidden">
                <label htmlFor="contact-website">Leave this field empty</label>
                <input id="contact-website" name="website" type="text" tabIndex={-1} autoComplete="off" />
              </div>
              <div className="grid gap-5 sm:grid-cols-2">
                <F label="Name" err={errors["name"]}><input name="name" maxLength={100} className={field} placeholder="Ada Lovelace" /></F>
                <F label="Email" err={errors["email"]}><input name="email" type="email" maxLength={255} className={field} placeholder="ada@mail.com" /></F>
              </div>
              <F label="Company (optional)"><input name="company" maxLength={120} className={field} placeholder="Analytical Engines Ltd" /></F>
              <div>
                <p className="mb-2 font-mono text-xs font-bold uppercase tracking-widest">Topic</p>
                <div className="flex flex-wrap gap-2">
                  {TOPICS.map((t) => (
                    <button type="button" key={t} onClick={() => setTopic(t)}
                      className={`brut-btn rounded-xl px-3 py-2 text-sm font-bold ${topic === t ? "bg-orange" : "bg-paper"}`}>{t}</button>
                  ))}
                </div>
              </div>
              <F label="Message" err={errors["message"]}><textarea name="message" rows={5} maxLength={2000} className={field} placeholder="Tell us what's on your mind…" /></F>
              {state === "error" && <p className="font-bold text-orange">Something went wrong — please try again.</p>}
              <button disabled={state === "sending"} className="brut-btn inline-flex items-center justify-center gap-2 rounded-2xl bg-orange px-6 py-4 text-lg font-bold hover:bg-orange-hover disabled:opacity-60">
                {state === "sending" ? "Sending…" : <>Send message <Send className="h-5 w-5" /></>}
              </button>
            </form>
          )}
        </motion.div>
      </main>
      <Footer />
    </div>
  );
}

function F({ label, err, children }: { label: string; err?: string | undefined; children: React.ReactNode }) {
  return (
    <label className="grid gap-2">
      <span className="font-mono text-xs font-bold uppercase tracking-widest">{label}</span>
      {children}
      {err && <span className="text-sm font-bold text-orange">{err}</span>}
    </label>
  );
}
