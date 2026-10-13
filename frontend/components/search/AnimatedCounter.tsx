"use client";

import { useEffect, useState } from "react";

export function AnimatedCounter({
  value,
  duration = 1200,
  decimals = 0,
}: {
  value: number;
  duration?: number;
  decimals?: number;
}) {
  const [count, setCount] = useState(0);

  useEffect(() => {
    let startTime: number;
    let frame: number;

    const animate = (now: number) => {
      if (!startTime) startTime = now;
      const progress = Math.min((now - startTime) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setCount(Number((eased * value).toFixed(decimals)));
      if (progress < 1) frame = requestAnimationFrame(animate);
    };

    frame = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(frame);
  }, [value, duration, decimals]);

  return <span className="tabular-nums">{decimals > 0 ? count.toFixed(decimals) : count.toLocaleString()}</span>;
}
