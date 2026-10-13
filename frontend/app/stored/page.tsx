"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Library, Download, Trash2, ExternalLink, ChevronLeft, ChevronRight } from "lucide-react";
import { listSources, downloadSource, deleteSource, SOURCE_TYPES, SourceItem, API_URL } from "@/lib/api";
import { getSourceTheme } from "@/lib/sourceTheme";
import {
  Badge,
  Card,
  CardSkeleton,
  EmptyState,
  PageHeader,
} from "@/components/ui";
import { ThumbImage } from "@/components/ThumbImage";

export default function StoredPage() {
  const [filter, setFilter] = useState("");
  const [page, setPage] = useState(1);
  const pageSize = 20;
  const queryClient = useQueryClient();
  
  const { data, isLoading } = useQuery({
    queryKey: ["sources", filter, page],
    queryFn: () => listSources(filter || undefined, page, pageSize),
    refetchInterval: 5000,
    refetchIntervalInBackground: false,
  });

  const deleteMutation = useMutation({
    mutationFn: (sourceId: string) => deleteSource(sourceId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sources"] });
    },
  });

  const handleDownload = (source: SourceItem) => {
    if (source.file_path) {
      downloadSource(source.source_id, source.file_name);
    }
  };

  const handleDelete = (sourceId: string) => {
    if (confirm("Are you sure you want to delete this source? This action cannot be undone.")) {
      deleteMutation.mutate(sourceId);
    }
  };

  const formatFileSize = (bytes?: number) => {
    if (!bytes) return "";
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const canDownload = (source: SourceItem) => {
    return source.file_path && ["pdf", "document", "audio"].includes(source.source_type);
  };

  const getOpenUrl = (source: SourceItem): string | null => {
    if (source.url && /^https?:\/\//.test(source.url)) return source.url;
    if (source.channel && /^https?:\/\//.test(source.channel)) return source.channel;
    return null;
  };

  const canOpenOriginal = (source: SourceItem) => getOpenUrl(source) !== null;

  const canViewInline = (source: SourceItem) =>
    !!source.file_path && ["pdf", "document", "audio"].includes(source.source_type);

  const totalPages = data?.total_pages ?? 1;

  return (
    <div className="max-w-4xl text-foreground">
      <PageHeader
        title="Stored Sources"
        subtitle={`Everything indexed in your knowledge base. ${data?.total ?? 0} total sources.`}
      />

      <div className="mb-6 flex flex-wrap gap-2">
        {SOURCE_TYPES.map((f) => {
          const active = filter === f;
          return (
            <button
              key={f || "all"}
              onClick={() => { setFilter(f); setPage(1); }}
              className={`rounded-full px-3 py-1 text-xs capitalize transition border ${
                active
                  ? "bg-brand border-brand text-ink font-medium shadow-sm"
                  : "bg-surface border-border text-muted hover:bg-surface-muted hover:text-foreground"
              }`}
            >
              {f || "all"}
            </button>
          );
        })}
      </div>

      {isLoading && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <CardSkeleton />
          <CardSkeleton />
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {data?.items.map((s) => {
          const srcTheme = getSourceTheme(s.source_type);
          const Icon = srcTheme.icon;
          return (
            <Card key={s.source_id} className="p-4 relative group flex flex-col justify-between">
              <div>
                {s.thumbnail && (
                  <div className="mb-2 -mx-4 -mt-4">
                    <ThumbImage
                      src={s.thumbnail}
                      alt={s.title || "Thumbnail"}
                      className="w-full h-32 object-cover rounded-t-lg"
                      fallbackClassName="h-32 rounded-t-lg"
                    />
                  </div>
                )}
                <div className="mb-1.5 flex items-center gap-2">
                  <Icon className="h-3.5 w-3.5" style={{ color: srcTheme.accent }} />
                  <span className="text-xs font-semibold uppercase tracking-wide text-muted">
                    {s.source_type}
                  </span>
                  {s.file_size && (
                    <span className="ml-auto text-[10px] text-subtle">{formatFileSize(s.file_size)}</span>
                  )}
                </div>
                <h3 className="mb-1 font-medium text-foreground">
                  {getOpenUrl(s) ? (
                    <a
                      href={getOpenUrl(s) ?? undefined}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="hover:text-brand transition-colors"
                    >
                      {s.title || s.source_id}
                    </a>
                  ) : canViewInline(s) ? (
                    <a
                      href={`/source/${encodeURIComponent(s.source_id)}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="hover:text-brand transition-colors"
                    >
                      {s.title || s.source_id}
                    </a>
                  ) : (
                    s.title || s.source_id
                  )}
                </h3>
                {s.channel && (
                  <p className="mb-2 text-xs text-muted truncate">{s.channel}</p>
                )}
                <p className="line-clamp-3 text-sm text-foreground-3">{s.summary}</p>
                <div className="mt-3 flex flex-wrap gap-1">
                  {s.key_topics.slice(0, 4).map((t) => (
                    <Badge key={t}>{t}</Badge>
                  ))}
                </div>
              </div>

              {/* Action buttons */}
              <div className="mt-4 flex flex-wrap items-center gap-2 opacity-100 transition-opacity md:opacity-0 md:group-hover:opacity-100 md:group-focus-within:opacity-100">
                {canDownload(s) && (
                  <button
                    onClick={() => handleDownload(s)}
                    className="flex items-center gap-1 rounded-lg bg-brand-soft px-3 py-1.5 text-xs text-brand hover:bg-brand-soft/80 transition"
                  >
                    <Download className="h-3 w-3" />
                    Download
                  </button>
                )}
                {canViewInline(s) && (
                  <a
                    href={`/source/${encodeURIComponent(s.source_id)}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1 rounded-lg bg-info/10 px-3 py-1.5 text-xs text-info hover:bg-info/20 transition"
                  >
                    <ExternalLink className="h-3 w-3" />
                    Open
                  </a>
                )}
                {canOpenOriginal(s) && (
                  <a
                    href={getOpenUrl(s) ?? undefined}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1 rounded-lg bg-surface border-2 border-ink px-3 py-1.5 text-xs text-muted hover:bg-surface-muted hover:text-foreground transition"
                  >
                    <ExternalLink className="h-3 w-3" />
                    Open
                  </a>
                )}
                <button
                  onClick={() => handleDelete(s.source_id)}
                  disabled={deleteMutation.isPending}
                  className="flex items-center gap-1 rounded-lg bg-danger/10 px-3 py-1.5 text-xs text-danger hover:bg-danger/20 transition ml-auto"
                >
                  <Trash2 className="h-3 w-3" />
                  Delete
                </button>
              </div>
            </Card>
          );
        })}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="mt-6 flex items-center justify-center gap-2">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="flex items-center gap-1 rounded-lg border-2 border-ink bg-surface px-3 py-2 text-xs text-muted hover:bg-surface-muted hover:text-foreground disabled:opacity-30 disabled:cursor-not-allowed transition"
          >
            <ChevronLeft className="h-3 w-3" />
            Previous
          </button>
          <span className="text-xs text-subtle">
            Page {page} of {totalPages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="flex items-center gap-1 rounded-lg border-2 border-ink bg-surface px-3 py-2 text-xs text-muted hover:bg-surface-muted hover:text-foreground disabled:opacity-30 disabled:cursor-not-allowed transition"
          >
            Next
            <ChevronRight className="h-3 w-3" />
          </button>
        </div>
      )}

      {data && data.items.length === 0 && !isLoading && (
        <EmptyState
          icon={<Library className="h-6 w-6" />}
          title="No sources yet"
          hint="Add a YouTube video, PDF, or web page to get started."
        />
      )}
    </div>
  );
}
