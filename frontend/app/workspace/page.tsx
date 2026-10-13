"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { createNote, deleteNote, listNotes } from "@/lib/api";
import { Trash2, Plus } from "lucide-react";

const TOOLS = [
  { href: "/youtube", label: "YouTube" },
  { href: "/instagram", label: "Instagram" },
  { href: "/chat", label: "Ask AI" },
  { href: "/graph", label: "Knowledge Graph" },
  { href: "/stored", label: "Stored" },
];

export default function WorkspacePage() {
  const queryClient = useQueryClient();
  const { data: notes } = useQuery({ queryKey: ["notes"], queryFn: listNotes });
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");

  const create = useMutation({
    mutationFn: () => createNote(title, body),
    onSuccess: () => {
      setTitle("");
      setBody("");
      queryClient.invalidateQueries({ queryKey: ["notes"] });
    },
  });

  const remove = useMutation({
    mutationFn: deleteNote,
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["notes"] }),
  });

  return (
    <div className="max-w-4xl">
      <h1 className="mb-1 text-2xl font-semibold">AI Workspace</h1>
      <p className="mb-6 text-sm text-gray-400">
        Your notes, collections, and every MindMesh tool in one place.
      </p>

      <div className="mb-8 grid grid-cols-2 gap-3 sm:grid-cols-3">
        {TOOLS.map((t) => (
          <Link
            key={t.href}
            href={t.href}
            className="rounded-xl border-2 border-ink bg-surface p-4 text-sm font-medium transition hover:border-brand"
          >
            {t.label}
          </Link>
        ))}
      </div>

      <h2 className="mb-3 text-sm font-semibold text-gray-300">Notes</h2>

      <div className="mb-6 rounded-xl border-2 border-ink bg-surface p-4">
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Note title"
          className="mb-2 w-full rounded-lg border-2 border-ink bg-surface px-3 py-2 text-sm outline-none focus:border-brand"
        />
        <textarea
          value={body}
          onChange={(e) => setBody(e.target.value)}
          placeholder="Write something..."
          rows={3}
          className="mb-2 w-full rounded-lg border-2 border-ink bg-surface px-3 py-2 text-sm outline-none focus:border-brand"
        />
        <button
          onClick={() => title && create.mutate()}
          disabled={create.isPending || !title}
          className="flex items-center gap-2 rounded-lg bg-brand px-4 py-2 text-sm font-medium disabled:opacity-50"
        >
          <Plus className="h-4 w-4" />
          Add note
        </button>
      </div>

      <div className="space-y-3">
        {notes?.map((n) => (
          <div
            key={n.id}
            className="flex items-start justify-between rounded-xl border-2 border-ink bg-surface p-4"
          >
            <div>
              <h3 className="font-medium">{n.title}</h3>
              <p className="whitespace-pre-wrap text-sm text-gray-400">{n.body}</p>
            </div>
            <button
              onClick={() => remove.mutate(n.id)}
              className="text-gray-500 hover:text-red-400"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          </div>
        ))}
        {notes && notes.length === 0 && (
          <p className="text-sm text-gray-400">No notes yet.</p>
        )}
      </div>
    </div>
  );
}
