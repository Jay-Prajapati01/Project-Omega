"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { ArrowRight, LockKeyhole, Mail, Loader2 } from "lucide-react";
import { useAuth } from "./CloudAuthGate";
import { getSupabase } from "@/lib/supabaseClient";

type Mode = "login" | "signup" | "forgot" | "reset";
const titles = { login: "Welcome back.", signup: "Your knowledge. Connected.", forgot: "Forgot your password?", reset: "Choose a new password." };
const actions = { login: "Sign in", signup: "Create account", forgot: "Send reset link", reset: "Save password" };

function destination() {
  const next = new URLSearchParams(window.location.search).get("next");
  if (!next || !next.startsWith("/") || next.startsWith("//") || next.includes("\\")) return "/dashboard";
  const url = new URL(next, window.location.origin);
  return url.origin === window.location.origin && !["/login", "/signup", "/reset-password", "/forgot-password"].includes(url.pathname) ? url.pathname + url.search : "/dashboard";
}

export function AuthForm({ mode }: { mode: Mode }) {
  const { session, ready, error: configError } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const newPassword = mode === "signup" || mode === "reset";

  async function googleSignIn() {
    setBusy(true); setError(""); setMessage("");
    try {
      const { error: failure } = await getSupabase().auth.signInWithOAuth({
        provider: "google",
        options: { redirectTo: `${window.location.origin}${destination()}` },
      });
      if (failure) throw failure;
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Unable to start Google sign-in.");
    } finally { setBusy(false); }
  }

  useEffect(() => {
    if (ready && session && (mode === "login" || mode === "signup")) router.replace(destination());
  }, [ready, session, mode, router]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true); setError(""); setMessage("");
    try {
      const auth = getSupabase().auth;
      if (newPassword && password !== confirm) throw new Error("The passwords do not match.");
      if (mode === "signup") {
        const result = await auth.signUp({ email: email.trim(), password, options: { emailRedirectTo: `${window.location.origin}/dashboard` } });
        if (result.error) throw result.error;
        setPassword(""); setConfirm("");
        if (!result.data.session) setMessage("Check your email to confirm your account. You can sign in after confirming.");
      } else if (mode === "login") {
        const { error: failure } = await auth.signInWithPassword({ email: email.trim(), password });
        if (failure) throw new Error("Unable to sign in. Check your email and password, and confirm your email if you just signed up.");
      } else if (mode === "forgot") {
        const { error: failure } = await auth.resetPasswordForEmail(email.trim(), { redirectTo: `${window.location.origin}/reset-password` });
        if (failure) throw failure;
        setMessage("If an account exists for this email, you will receive a password reset link.");
      } else {
        const { error: failure } = await auth.updateUser({ password });
        if (failure) throw failure;
        setMessage("Password updated. Your workspace is ready.");
        setPassword(""); setConfirm("");
      }
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Unable to continue. Please try again.");
    } finally { setBusy(false); }
  }

  const field = "mt-2 block w-full rounded-xl border-2 border-ink bg-sheet px-4 py-3 text-ink outline-none focus:ring-2 focus:ring-orange focus:ring-offset-2";
  return <main className="paper-grain min-h-screen bg-paper px-5 py-8 text-ink sm:py-12">
    <Link href="/" className="mx-auto flex w-fit items-center gap-2 text-xl font-extrabold"><Image src="/logo.png" width={38} height={38} alt="" className="rounded-lg bg-black p-1" />MindMesh</Link>
    <div className="mx-auto mt-10 grid max-w-4xl overflow-hidden rounded-3xl border-2 border-ink bg-sheet shadow-[6px_6px_0_var(--ink)] md:grid-cols-[0.85fr_1.15fr]">
      <aside className="border-b-2 border-ink bg-orange p-7 md:border-b-0 md:border-r-2 md:p-9">
        <LockKeyhole className="h-9 w-9" />
        <p className="mt-6 font-mono text-xs font-bold uppercase tracking-widest">Your personal workspace</p>
        <h1 className="mt-4 font-display text-4xl uppercase leading-tight sm:text-5xl">{titles[mode]}</h1>
        <p className="mt-5 leading-relaxed">Save your sources, connect your ideas, and ask questions across your knowledge. Your library belongs to your account.</p>
      </aside>
      <section className="p-7 md:p-9">
        <h2 className="text-2xl font-extrabold">{actions[mode]}</h2>
        <p className="mt-2 text-sm text-ink-muted">{mode === "signup" ? "Start with your email and a secure password." : mode === "forgot" ? "We’ll email you a link to reset your password." : mode === "reset" ? "Use at least 8 characters." : "Pick up where you left off."}</p>
        <form onSubmit={submit} className="mt-7 space-y-5">
          {mode !== "reset" && <label className="block text-sm font-bold">Email<input name="email" type="email" required autoComplete="email" value={email} onChange={e => setEmail(e.target.value)} className={field} placeholder="you@example.com" /></label>}
          {mode !== "forgot" && <label className="block text-sm font-bold">Password<input name="password" type="password" required minLength={newPassword ? 8 : undefined} autoComplete={newPassword ? "new-password" : "current-password"} value={password} onChange={e => setPassword(e.target.value)} className={field} /></label>}
          {newPassword && <label className="block text-sm font-bold">Confirm password<input name="confirmPassword" type="password" required minLength={8} autoComplete="new-password" value={confirm} onChange={e => setConfirm(e.target.value)} className={field} /></label>}
          {mode === "login" && <Link href="/forgot-password" className="block text-sm font-bold underline">Forgot password?</Link>}
          {(error || configError) && <p role="alert" className="rounded-xl border border-red-500 bg-red-50 p-3 text-sm text-red-800">{error || configError}</p>}
          {mode === "reset" && ready && !session && <p role="alert">Open the reset link in your email first. <Link href="/forgot-password" className="underline">Request a new link</Link>.</p>}
          {message && <p role="status" className="flex gap-2 rounded-xl border border-ink bg-paper p-3 text-sm"><Mail className="h-5 w-5 shrink-0" />{message}</p>}
          <button type="submit" disabled={busy || !ready || !!configError || (mode === "reset" && !session)} className="brut-btn flex w-full items-center justify-center gap-2 rounded-xl bg-orange px-5 py-3 font-bold disabled:cursor-not-allowed disabled:opacity-50">{busy ? <Loader2 className="h-5 w-5 animate-spin" /> : <ArrowRight className="h-5 w-5" />}{busy ? "Please wait…" : actions[mode]}</button>
        </form>
        {(mode === "login" || mode === "signup") && <button type="button" onClick={googleSignIn} disabled={busy || !ready || !!configError} className="mt-4 w-full rounded-xl border-2 border-ink px-5 py-3 font-bold disabled:opacity-50">Continue with Google</button>}
        <p className="mt-6 text-sm">{mode === "signup" ? "Already have an account? " : mode === "login" ? "New to MindMesh? " : "Ready to continue? "}<Link href={mode === "login" ? "/signup" : mode === "reset" && session ? "/dashboard" : "/login"} className="font-bold underline">{mode === "login" ? "Create account" : mode === "reset" && session ? "Open workspace" : "Sign in"}</Link></p>
      </section>
    </div>
  </main>;
}
