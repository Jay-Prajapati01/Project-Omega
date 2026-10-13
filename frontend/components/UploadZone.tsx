"use client";

import { useState, useCallback, useRef } from "react";
import { Upload, CheckCircle, AlertCircle } from "lucide-react";

function matchesAccept(file: File, accept: string): boolean {
  if (!accept || accept.trim() === "" || accept === "*") return true;
  const patterns = accept.split(",").map((s) => s.trim().toLowerCase()).filter(Boolean);
  const name = file.name.toLowerCase();
  return patterns.some((p) => {
    if (p.startsWith(".")) return name.endsWith(p);
    if (p.endsWith("/*")) return file.type.startsWith(p.slice(0, -1));
    return file.type === p;
  });
}

export function UploadZone({
  file,
  accept,
  label,
  onSelect,
  disabled = false,
  hint,
}: {
  file: File | null;
  accept: string;
  label: string;
  onSelect: (file: File | null) => void;
  disabled?: boolean;
  hint?: string;
}) {
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const dragCounter = useRef(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const pick = useCallback(
    (next: File | null) => {
      if (next && !matchesAccept(next, accept)) {
        setError(`"${next.name}" is not a supported file type for this uploader`);
        return;
      }
      setError(null);
      onSelect(next);
    },
    [accept, onSelect]
  );

  const handleDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounter.current++;
    if (e.dataTransfer.types.includes("Files")) {
      setDragging(true);
    }
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounter.current--;
    if (dragCounter.current <= 0) {
      dragCounter.current = 0;
      setDragging(false);
    }
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      dragCounter.current = 0;
      setDragging(false);
      if (disabled) return;
      const droppedFile = e.dataTransfer.files?.[0];
      if (droppedFile) {
        pick(droppedFile);
      }
    },
    [disabled, pick]
  );

  const handleClick = () => {
    if (!disabled && inputRef.current) {
      inputRef.current.click();
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const next = e.target.files?.[0] ?? null;
    e.target.value = "";
    if (next) pick(next);
  };

  return (
    <div
      onDragEnter={handleDragEnter}
      onDragLeave={handleDragLeave}
      onDragOver={handleDragOver}
      onDrop={handleDrop}
      onClick={handleClick}
      className={`
        relative flex flex-col items-center gap-3 rounded-xl border-2 border-dashed p-10 text-center transition-all duration-200
        ${disabled ? "cursor-not-allowed opacity-50" : "cursor-pointer"}
        ${error
          ? "border-danger/50 bg-danger/5"
          : dragging
            ? "border-brand bg-brand-soft shadow-elevated"
            : file
              ? "border-success/40 bg-success/5 hover:border-success/60"
              : "border-border bg-surface hover:border-brand/50 hover:bg-brand-soft/20"
        }
      `}
    >
      {dragging && (
        <div className="absolute inset-0 rounded-xl flex items-center justify-center bg-brand-soft backdrop-blur-sm z-10">
          <div className="flex flex-col items-center gap-2">
            <Upload className="h-8 w-8 text-brand animate-bounce" />
            <span className="text-[13px] font-medium text-brand">Drop your file here</span>
          </div>
        </div>
      )}
      {error && (
        <div className="flex items-center justify-center gap-1.5 text-danger">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span className="text-[12px] font-medium">{error}</span>
        </div>
      )}
      {file ? (
        <>
          <CheckCircle className="h-6 w-6 text-success" />
          <span className="text-sm text-foreground-2">{file.name}</span>
          <span className="text-[11px] text-subtle">Click or drop to replace</span>
        </>
      ) : (
        <>
          <Upload className="h-6 w-6 text-brand" />
          <span className="text-sm text-foreground">{label}</span>
          <span className="text-[11px] text-muted">{hint || "Drag & drop or click to browse"}</span>
        </>
      )}
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        className="hidden"
        aria-label={label || "Upload file"}
        disabled={disabled}
        onChange={handleChange}
      />
    </div>
  );
}
