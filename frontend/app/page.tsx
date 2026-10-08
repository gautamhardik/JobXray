"use client";

// Investigation workspace: spec.md > Components > Frontend > app/page.tsx.

import { useState } from "react";

import PasteBox from "@/components/PasteBox";
import { startInvestigation, type InvestigationResult } from "@/lib/api";

export default function Home() {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<InvestigationResult | null>(null);

  async function investigate() {
    setBusy(true);
    setError(null);
    try {
      setResult(await startInvestigation(text));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main>
      <header>
        <div className="brand">JobXray</div>
        <div className="tagline">X-ray the job before you apply.</div>
      </header>

      {result ? (
        <section className="result" aria-live="polite">
          <div className="decision">{result.decision}</div>
          <div className="severity">{result.severity}</div>
          <p>{result.summary}</p>
          <div className="result-actions">
            <button
              type="button"
              className="link"
              onClick={() => {
                setResult(null);
                setText("");
              }}
            >
              Start a new investigation
            </button>
          </div>
        </section>
      ) : (
        <>
          <PasteBox value={text} onChange={setText} onSubmit={investigate} busy={busy} />
          {error && <p className="message">{error}</p>}
        </>
      )}
    </main>
  );
}
