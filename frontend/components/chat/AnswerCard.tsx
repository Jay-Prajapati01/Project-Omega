"use client";

import { useMemo } from "react";
import { motion } from "framer-motion";
import type { ReactNode } from "react";
import { ChatResponse } from "@/lib/api";
import { InlineCitation } from "./InlineCitation";
import { AssistantAvatar } from "./AssistantAvatar";

interface Props {
  response: ChatResponse;
  index: number;
}

function parseAnswerWithSections(answer: string) {
  const sections: { type: "heading" | "paragraph" | "list"; content: string; items?: string[] }[] = [];
  const lines = answer.split("\n");

  let currentParagraph = "";

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) {
      if (currentParagraph) {
        sections.push({ type: "paragraph", content: currentParagraph });
        currentParagraph = "";
      }
      continue;
    }

    if (/^#{1,6}\s+/.test(trimmed) || (trimmed.startsWith("**") && trimmed.endsWith("**"))) {
      if (currentParagraph) {
        sections.push({ type: "paragraph", content: currentParagraph });
        currentParagraph = "";
      }
      sections.push({ type: "heading", content: trimmed.replace(/^#{1,6}\s+/, "").replace(/\*\*/g, "") });
    } else if (trimmed.match(/^[-•*]\s/)) {
      if (currentParagraph) {
        sections.push({ type: "paragraph", content: currentParagraph });
        currentParagraph = "";
      }
      if (!sections.length || sections[sections.length - 1].type !== "list") {
        sections.push({ type: "list", content: "", items: [] });
      }
      sections[sections.length - 1].items!.push(trimmed.replace(/^[-•*]\s/, ""));
    } else {
      currentParagraph += (currentParagraph ? " " : "") + trimmed;
    }
  }

  if (currentParagraph) {
    sections.push({ type: "paragraph", content: currentParagraph });
  }

  return sections;
}

function renderMarkdownInline(text: string): ReactNode[] {
  const parts: ReactNode[] = [];
  const pattern = /(\*\*[^*]+\*\*|(?<!\*)\*[^*]+\*(?!\*)|`[^`]+`)/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  let key = 0;
  while ((match = pattern.exec(text)) !== null) {
    if (match.index > lastIndex) parts.push(text.slice(lastIndex, match.index));
    const token = match[0];
    const value = token.startsWith("**") ? token.slice(2, -2) : token.slice(1, -1);
    if (token.startsWith("**")) parts.push(<strong key={key++} className="font-semibold text-foreground">{value}</strong>);
    else if (token.startsWith("`")) parts.push(<code key={key++} className="rounded bg-surface px-1 py-0.5 text-[0.92em]">{value}</code>);
    else parts.push(<em key={key++}>{value}</em>);
    lastIndex = pattern.lastIndex;
  }
  if (lastIndex < text.length) parts.push(text.slice(lastIndex));
  return parts;
}

function renderWithCitations(text: string, citations: { source_id: string; source_type: string; title?: string; snippet: string; url?: string; thumbnail?: string }[]) {
  const parts: (string | { type: "citation"; index: number; citation: typeof citations[0] })[] = [];
  const regex = /\[(?:source\s*)?(\d+)\]/gi;
  let lastIndex = 0;
  let match;

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }
    const num = parseInt(match[1], 10);
    if (num >= 1 && num <= citations.length) {
      parts.push({ type: "citation", index: num, citation: citations[num - 1] });
    }
    lastIndex = regex.lastIndex;
  }
  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }
  return parts;
}

export function AnswerCard({ response, index }: Props) {
  const sections = useMemo(() => parseAnswerWithSections(response.answer), [response.answer]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: index * 0.1 }}
      className="flex items-start gap-3"
    >
      <AssistantAvatar />

      <div className="min-w-0 flex-1 rounded-[16px] rounded-tl-[4px] border-2 border-ink bg-card px-5 py-4">
        <div className="max-w-none space-y-4 text-[14px] leading-[1.8] text-foreground-2">
          {sections.map((section, i) => {
            if (section.type === "heading") {
              return (
                <h3 key={i} className="pt-2 text-[15px] font-semibold text-foreground">
                  {section.content}
                </h3>
              );
            }
            if (section.type === "list") {
              return (
                <ul key={i} className="space-y-2 pl-1">
                  {section.items?.map((item, j) => (
                    <li key={j} className="flex items-start gap-2.5">
                      <span className="mt-1.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-[#FF5C00]" />
                      <span>{renderMarkdownInline(item)}</span>
                    </li>
                  ))}
                </ul>
              );
            }
            return (
              <div key={i}>
                {renderWithCitations(section.content, response.citations).map((part, pi) =>
                  typeof part === "string" ? renderMarkdownInline(part) : (
                    <InlineCitation
                      key={pi}
                      index={part.index}
                      sourceTitle={part.citation.title || part.citation.source_id}
                      sourceType={part.citation.source_type}
                      snippet={part.citation.snippet}
                      url={["pdf", "document", "audio"].includes(part.citation.source_type) ? `/source/${encodeURIComponent(part.citation.source_id)}` : part.citation.url}
                    />
                  )
                )}
              </div>
            );
          })}
        </div>
      </div>
    </motion.div>
  );
}
