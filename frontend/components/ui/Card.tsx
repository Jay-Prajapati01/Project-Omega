import { HTMLAttributes } from "react";

export function Card({
  className = "",
  children,
  ...props
}: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={`brut bg-card p-5 text-foreground transition-all ${className}`}
      {...props}
    >
      {children}
    </div>
  );
}
