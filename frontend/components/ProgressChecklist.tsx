"use client";

// Live investigation progress: spec.md > Components > Frontend > components/ProgressChecklist.tsx.
// Polls every 1.5 seconds and stops when the investigation is done or failed.

import { useEffect, useRef, useState } from "react";

import { getInvestigation, type InvestigationResult, type Step } from "@/lib/api";

const POLL_MS = 1500;

type Props = {
  id: string;
  onDone: (result: InvestigationResult) => void;
  onFailed: (message: string) => void;
};

const MARK: { [key in Step["state"]]: string } = {
  pending: "○",
  active: "◌",
  done: "✓",
  skipped: "–",
};

export default function ProgressChecklist({ id, onDone, onFailed }: Props) {
  const [steps, setSteps] = useState<Step[]>([]);
  const callbacks = useRef({ onDone, onFailed });
  callbacks.current = { onDone, onFailed };

  useEffect(() => {
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;

    async function poll() {
      try {
        const status = await getInvestigation(id);
        if (stopped) return;
        setSteps(status.steps);
        if (status.status === "done" && status.result) return callbacks.current.onDone(status.result);
        if (status.status === "failed") return callbacks.current.onFailed(status.error ?? "Analysis could not finish.");
        timer = setTimeout(poll, POLL_MS);
      } catch (err) {
        if (!stopped) callbacks.current.onFailed(err instanceof Error ? err.message : "Analysis could not finish.");
      }
    }

    poll();
    return () => {
      stopped = true;
      clearTimeout(timer);
    };
  }, [id]);

  return (
    <section className="progress" aria-live="polite" aria-busy="true">
      <div className="scan" aria-hidden="true" />
      <div className="progress-title">Investigating the opportunity</div>
      <ol className="steps">
        {steps.map((step) => (
          <li key={step.key} className={`step step-${step.state}`}>
            <span className="step-mark" aria-hidden="true">
              {MARK[step.state]}
            </span>
            <span>
              {step.label}
              {step.note && <span className="step-note"> · {step.note}</span>}
            </span>
          </li>
        ))}
      </ol>
      <p className="muted small">Free models can take up to a minute or two.</p>
    </section>
  );
}
