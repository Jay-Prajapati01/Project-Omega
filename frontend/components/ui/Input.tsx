import { InputHTMLAttributes, TextareaHTMLAttributes } from "react";

const BASE =
  "w-full rounded-xl border-2 border-ink bg-surface text-foreground px-4 py-2 text-sm font-medium outline-none transition focus:border-ink focus:shadow-brut placeholder:text-muted";

export function Input(props: InputHTMLAttributes<HTMLInputElement>) {
  const { className = "", ...rest } = props;
  return <input className={`${BASE} ${className}`} {...rest} />;
}

export function Textarea(props: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  const { className = "", ...rest } = props;
  return <textarea className={`${BASE} ${className}`} {...rest} />;
}
