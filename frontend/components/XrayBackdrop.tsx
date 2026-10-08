"use client";

// The X-ray beam behind the page: ThreeUI Community's LaserCollection (MIT, @designcodeio/threeui).
// WebGL only runs in the browser, so it loads without server rendering. The beam reacts to the
// pointer; the page above it keeps receiving clicks, so pointer moves are forwarded to the beam.
// Respects reduced motion.

import dynamic from "next/dynamic";
import { useEffect, useRef, useState } from "react";

const LaserCollection = dynamic(
  () => import("@designcodeio/threeui/components/LaserCollection").then((m) => m.LaserCollection),
  { ssr: false },
);

type Props = {
  phase: "input" | "running" | "result";
};

export default function XrayBackdrop({ phase }: Props) {
  const [reduced, setReduced] = useState(false);
  const host = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduced(query.matches);
    const update = () => setReduced(query.matches);
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);

  useEffect(() => {
    function forward(event: PointerEvent) {
      const target = host.current?.querySelector(".threeui-background");
      target?.dispatchEvent(
        new PointerEvent(event.type, {
          clientX: event.clientX,
          clientY: event.clientY,
          pointerId: event.pointerId,
          pointerType: event.pointerType,
        }),
      );
    }
    window.addEventListener("pointermove", forward, { passive: true });
    document.documentElement.addEventListener("pointerleave", forward);
    return () => {
      window.removeEventListener("pointermove", forward);
      document.documentElement.removeEventListener("pointerleave", forward);
    };
  }, []);

  if (reduced) return <div className="backdrop backdrop-static" aria-hidden="true" />;

  return (
    <div ref={host} className={`backdrop backdrop-${phase}`} aria-hidden="true">
      <LaserCollection
        variant="atmospheric-blade"
        speed={phase === "running" ? 2.2 : 1}
        brightness={phase === "result" ? 0.55 : 1.1}
        hue={70}
        style={{ width: "100%", height: "100%" }}
      />
    </div>
  );
}
