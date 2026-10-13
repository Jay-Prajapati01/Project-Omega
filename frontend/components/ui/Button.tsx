"use client";

import { Loader2 } from "lucide-react";
import { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "ghost" | "danger";

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  loading?: boolean;
}

const VARIANTS: Record<Variant, string> = {
  primary: "brut-btn bg-brand text-ink hover:bg-brand-hover font-bold",
  secondary: "brut-btn bg-surface text-foreground hover:bg-surface-muted font-bold",
  ghost: "bg-transparent text-foreground-2 hover:bg-surface hover:text-foreground rounded-lg",
  danger: "brut-btn bg-danger text-ink hover:opacity-90 font-bold",
};

export function Button({
  variant = "primary",
  loading = false,
  disabled,
  children,
  className = "",
  ...props
}: Props) {
  return (
    <button
      disabled={disabled || loading}
      className={`inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-50 ${VARIANTS[variant]} ${className}`}
      {...props}
    >
      {loading && <Loader2 className="h-4 w-4 animate-spin" />}
      {children}
    </button>
  );
}
