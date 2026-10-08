"use client";

// Decodes text from random glyphs into the final words, like a scan resolving.
// Plain text for screen readers; respects reduced motion.

import { useEffect, useState } from "react";

const GLYPHS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789#%/\\<>*+=";

type Props = {
  text: string;
  className?: string;
  duration?: number;
};

export default function ScrambleText({ text, className, duration = 1100 }: Props) {
  const [shown, setShown] = useState(text);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    let frame = 0;
    const start = performance.now();
    function tick(now: number) {
      const progress = Math.min(1, (now - start) / duration);
      const settled = Math.floor(progress * text.length);
      setShown(
        text
          .split("")
          .map((ch, i) => (i < settled || ch === " " ? ch : GLYPHS[Math.floor(Math.random() * GLYPHS.length)]))
          .join(""),
      );
      if (progress < 1) frame = requestAnimationFrame(tick);
    }
    frame = requestAnimationFrame(tick);
    // If the tab pauses animation frames, never leave the words scrambled.
    const settle = window.setTimeout(() => setShown(text), duration + 300);
    return () => {
      cancelAnimationFrame(frame);
      window.clearTimeout(settle);
    };
  }, [text, duration]);

  return (
    <span className={className} aria-label={text}>
      <span aria-hidden="true">{shown}</span>
    </span>
  );
}
