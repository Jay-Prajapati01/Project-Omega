import { HTMLAttributes } from "react";

export function Badge({
  className = "",
  children,
  ...props
}: HTMLAttributes<HTMLSpanElement>) {
  return (
    <span
      className={`inline-block rounded-full bg-brand-soft border-2 border-ink px-2.5 py-0.5 text-xs font-bold text-foreground ${className}`}
      {...props}
    >
      {children}
    </span>
  );
}
