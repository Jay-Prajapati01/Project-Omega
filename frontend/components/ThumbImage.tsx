"use client";

import { useState } from "react";

interface ThumbImageProps {
  src?: string | null;
  alt?: string;
  className?: string;
  fallbackClassName?: string;
}

export function ThumbImage({
  src,
  alt = "",
  className = "",
  fallbackClassName = "",
}: ThumbImageProps) {
  const [failed, setFailed] = useState(false);

  if (!src || failed) {
    return (
      <div
        aria-hidden="true"
        className={`flex items-center justify-center bg-surface border-2 border-ink ${className} ${fallbackClassName}`}
      />
    );
  }

  return (
    <img
      src={src}
      alt={alt}
      loading="lazy"
      className={className}
      referrerPolicy="no-referrer"
      onError={() => setFailed(true)}
    />
  );
}
