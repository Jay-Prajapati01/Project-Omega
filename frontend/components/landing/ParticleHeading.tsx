import { useEffect, useRef } from "react";

type Particle = {
  x: number;
  y: number;
  tx: number;
  ty: number;
  vx: number;
  vy: number;
  orange: boolean;
  seed: number;
};

const COPY = "YOU SAW IT. MINDMESH REMEMBERS.";

export function ParticleHeading() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const context = canvas.getContext("2d", { alpha: true });
    if (!context) return;

    let frame = 0;
    let particles: Particle[] = [];
    let pointerX = -10_000;
    let pointerY = -10_000;
    let visible = true;
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    const readColors = () => {
      const styles = getComputedStyle(document.documentElement);
      return {
        ink: styles.getPropertyValue("--ink").trim(),
        orange: styles.getPropertyValue("--orange").trim(),
      };
    };

    const build = () => {
      const width = canvas.clientWidth;
      const height = canvas.clientHeight;
      if (width < 1 || height < 1) return;
      const dpr = Math.min(window.devicePixelRatio || 1, 1.75);
      canvas.width = Math.round(width * dpr);
      canvas.height = Math.round(height * dpr);
      context.setTransform(dpr, 0, 0, dpr, 0, 0);

      const mask = document.createElement("canvas");
      mask.width = Math.max(1, Math.round(width));
      mask.height = Math.max(1, Math.round(height));
      const maskContext = mask.getContext("2d", { willReadFrequently: true });
      if (!maskContext) return;

      const lines = width < 620
        ? ["YOU SAW IT.", "MINDMESH", "REMEMBERS."]
        : ["YOU SAW IT.", "MINDMESH REMEMBERS."];
      const horizontalPadding = Math.max(8, width * 0.012);
      const verticalPadding = Math.max(8, height * 0.04);
      const maxWidth = width - horizontalPadding * 2;
      const maxHeight = height - verticalPadding * 2;
      let fontSize = Math.min(width / 8, maxHeight / lines.length);

      maskContext.font = `900 ${fontSize}px Anton, Impact, sans-serif`;
      const widest = Math.max(...lines.map((line) => maskContext.measureText(line).width));
      fontSize *= Math.min(1, maxWidth / widest, maxHeight / (lines.length * fontSize * 0.9));
      const lineHeight = fontSize * 0.9;
      const totalHeight = lineHeight * lines.length;
      const startY = (height - totalHeight) / 2 + fontSize * 0.78;
      maskContext.font = `900 ${fontSize}px Anton, Impact, sans-serif`;
      maskContext.textBaseline = "alphabetic";
      maskContext.textAlign = "left";

      lines.forEach((line, lineIndex) => {
        const lineWidth = maskContext.measureText(line).width;
        const x = (width - lineWidth) / 2;
        const y = startY + lineIndex * lineHeight;
        const askIndex = line.indexOf("REMEMBERS.");
        if (askIndex < 0) {
          maskContext.fillStyle = "rgb(0, 0, 0)";
          maskContext.fillText(line, x, y);
          return;
        }
        const before = line.slice(0, askIndex);
        maskContext.fillStyle = "rgb(0, 0, 0)";
        maskContext.fillText(before, x, y);
        maskContext.fillStyle = "rgb(255, 0, 0)";
        maskContext.fillText("REMEMBERS.", x + maskContext.measureText(before).width, y);
      });

      const pixels = maskContext.getImageData(0, 0, mask.width, mask.height).data;
      const gap = width < 500 ? 2 : width < 900 ? 3 : 3;
      const next: Particle[] = [];
      for (let y = 0; y < mask.height; y += gap) {
        for (let x = 0; x < mask.width; x += gap) {
          const pixel = (y * mask.width + x) * 4;
          if ((pixels[pixel + 3] ?? 0) < 90) continue;
          const orange = (pixels[pixel] ?? 0) > 120;
          const angle = Math.random() * Math.PI * 2;
          const distance = reducedMotion ? 0 : 8 + Math.random() * Math.min(34, width * 0.035);
          next.push({
            x: x + Math.cos(angle) * distance,
            y: y + Math.sin(angle) * distance,
            tx: x,
            ty: y,
            vx: 0,
            vy: 0,
            orange,
            seed: Math.random() * Math.PI * 2,
          });
        }
      }
      particles = next;
    };

    const draw = (time = 0) => {
      const box = canvas.getBoundingClientRect();
      const dpr = Math.min(window.devicePixelRatio || 1, 1.75);
      context.setTransform(dpr, 0, 0, dpr, 0, 0);
      context.clearRect(0, 0, box.width, box.height);
      const colors = readColors();
      const radius = box.width < 500 ? 0.95 : 1.15;
      const influence = Math.min(105, Math.max(62, box.width * 0.09));

      for (const particle of particles) {
        if (!reducedMotion) {
          const dx = particle.x - pointerX;
          const dy = particle.y - pointerY;
          const distance = Math.sqrt(dx * dx + dy * dy) || 1;
          if (distance < influence) {
            const force = (1 - distance / influence) * 1.5;
            particle.vx += (dx / distance) * force;
            particle.vy += (dy / distance) * force;
          }
          const drift = Math.sin(time * 0.0012 + particle.seed) * 0.018;
          particle.vx += (particle.tx - particle.x) * 0.075 + drift;
          particle.vy += (particle.ty - particle.y) * 0.075;
          particle.vx *= 0.76;
          particle.vy *= 0.76;
          particle.x += particle.vx;
          particle.y += particle.vy;
        }
        context.beginPath();
        context.fillStyle = particle.orange ? colors.orange : colors.ink;
        context.arc(particle.x, particle.y, radius, 0, Math.PI * 2);
        context.fill();
      }
      if (!reducedMotion && visible) frame = requestAnimationFrame(draw);
    };

    const onPointerMove = (event: PointerEvent) => {
      const box = canvas.getBoundingClientRect();
      pointerX = event.clientX - box.left;
      pointerY = event.clientY - box.top;
    };
    const clearPointer = () => { pointerX = -10_000; pointerY = -10_000; };
    const observer = new ResizeObserver(() => {
      cancelAnimationFrame(frame);
      build();
      draw();
    });
    const visibilityObserver = new IntersectionObserver(([entry]) => {
      visible = entry?.isIntersecting ?? false;
      if (visible && !reducedMotion) {
        cancelAnimationFrame(frame);
        frame = requestAnimationFrame(draw);
      }
    });
    const themeObserver = new MutationObserver(() => build());

    const initialise = async () => {
      await document.fonts.ready;
      build();
      draw();
      observer.observe(canvas);
      visibilityObserver.observe(canvas);
      themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
    };
    void initialise();
    canvas.addEventListener("pointermove", onPointerMove);
    canvas.addEventListener("pointerleave", clearPointer);

    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      visibilityObserver.disconnect();
      themeObserver.disconnect();
      canvas.removeEventListener("pointermove", onPointerMove);
      canvas.removeEventListener("pointerleave", clearPointer);
    };
  }, []);

  return (
    <h1 className="particle-heading relative w-full" aria-label={COPY}>
      <span className="sr-only">{COPY}</span>
      <canvas ref={canvasRef} aria-hidden="true" className="h-full w-full touch-pan-y" />
    </h1>
  );
}
