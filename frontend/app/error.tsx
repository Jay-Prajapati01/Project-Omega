"use client";

import { useEffect } from "react";
import { AlertTriangle, RefreshCw, Home } from "lucide-react";
import Link from "next/link";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Application error:", error);
  }, [error]);

  const isChunkLoadError = error?.message?.includes("Loading chunk") || 
                           error?.message?.includes("dynamically imported");

  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center px-4 text-center">
      <div className="mb-6 flex h-16 w-16 items-center justify-center rounded-full bg-red-500/10">
        <AlertTriangle className="h-8 w-8 text-red-500" />
      </div>
      
      <h2 className="mb-2 text-xl font-semibold text-foreground">
        Something went wrong
      </h2>
      
      <p className="mb-2 max-w-md text-sm text-foreground-3">
        {error.message || "An unexpected error occurred."}
      </p>
      
      {error.digest && (
        <p className="mb-4 text-xs text-muted">
          Error ID: {error.digest}
        </p>
      )}
      
      {isChunkLoadError && (
        <p className="mb-4 text-xs text-yellow-500">
          This may be caused by a new deployment. Please hard refresh (Ctrl+Shift+R).
        </p>
      )}
      
      <div className="flex items-center gap-3">
        <button
          onClick={reset}
          className="flex items-center gap-2 rounded-[12px] bg-[#FF5C00] border-2 border-ink px-5 py-2.5 text-[13px] font-medium text-ink transition-all hover:bg-[#E14E00]"
        >
          <RefreshCw className="h-4 w-4" />
          Try again
        </button>
        
        <Link
          href="/"
          className="flex items-center gap-2 rounded-[12px] border-2 border-ink bg-card px-5 py-2.5 text-[13px] font-medium text-foreground-3 transition-all hover:bg-surface hover:text-foreground"
        >
          <Home className="h-4 w-4" />
          Go home
        </Link>
      </div>
    </div>
  );
}
