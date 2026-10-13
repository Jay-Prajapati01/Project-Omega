"use client";

import Link from "next/link";
import { Brain, Sparkles, Youtube, Instagram, Library } from "lucide-react";

const SUGGESTED_QUESTIONS = [
  "Summarize the key ideas in my saved videos.",
  "What do my YouTube and Instagram saves have in common?",
  "What should I revisit from my recent saves?",
];

const QUICK_ACTIONS = [
  { icon: Youtube, label: "Save YouTube", href: "/youtube" },
  { icon: Instagram, label: "Save Instagram", href: "/instagram" },
  { icon: Library, label: "Browse Stored", href: "/stored" },
];

interface Props {
  onQuestionClick: (question: string) => void;
}

export function ChatEmptyState({ onQuestionClick }: Props) {
  return <div className="mx-auto flex max-w-2xl flex-col items-center px-5 py-12 text-center">
    <div className="grid h-14 w-14 place-items-center rounded-2xl border-2 border-ink bg-brand text-ink"><Brain className="h-7 w-7" /></div>
    <h2 className="mt-5 text-2xl font-extrabold">Ask your saved knowledge</h2>
    <p className="mt-2 max-w-lg text-sm text-muted">Save YouTube videos and Instagram posts first. Ask AI searches their indexed content and cites the sources it uses.</p>
    <div className="mt-6 grid w-full gap-2 sm:grid-cols-2">
      {SUGGESTED_QUESTIONS.map((question) => <button key={question} onClick={() => onQuestionClick(question)} className="rounded-xl border-2 border-ink bg-card p-3 text-left text-sm font-semibold transition hover:bg-surface"><Sparkles className="mb-2 h-4 w-4 text-brand" />{question}</button>)}
    </div>
    <div className="mt-7 flex flex-wrap justify-center gap-2">
      {QUICK_ACTIONS.map(({ icon: Icon, label, href }) => <Link key={href} href={href} className="flex items-center gap-2 rounded-lg border-2 border-ink bg-surface px-3 py-2 text-sm font-bold"><Icon className="h-4 w-4" />{label}</Link>)}
    </div>
  </div>;
}
