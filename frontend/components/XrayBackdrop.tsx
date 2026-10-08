"use client";

// The X-ray beam behind the page: ThreeUI Community's LaserCollection (MIT, @designcodeio/threeui).
// WebGL only runs in the browser, so it loads without server rendering. Respects reduced motion.

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";

const LaserCollection = dynamic(() => import("@designcodeio/threeui/components/LaserCollection").then((m) => m.LaserCollection), {
  ssr: false,
});

type Props = {
  phase: "input" | "running" | "result";
};

export default function XrayBackdrop({ phase }: Props) {
  const [reduced, setReduced] = useState(false);

  useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduced(query.matches);
    const update = () => setReduced(query.matches);
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);

  if (reduced) return <div className="backdrop backdrop-static" aria-hidden="true" />;

  return (
    <div className={`backdrop backdrop-${phase}`} aria-hidden="true">
      <LaserCollection
        variant="atmospheric-blade"
        speed={phase === "running" ? 1.6 : 0.7}
        brightness={phase === "result" ? 0.5 : 1}
        hue={70}
        style={{ width: "100%", height: "100%" }}
      />
    </div>
  );
}
