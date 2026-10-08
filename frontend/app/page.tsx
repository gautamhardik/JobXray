"use client";

// Investigation workspace: spec.md > Components > Frontend > app/page.tsx.

import { useState } from "react";

import PasteBox, { asLink } from "@/components/PasteBox";
import ProgressChecklist from "@/components/ProgressChecklist";
import ResultView from "@/components/ResultView";
import { startInvestigation, type InvestigationResult } from "@/lib/api";

export default function Home() {
  const [text, setText] = useState("");
  const [image, setImage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<InvestigationResult | null>(null);
  const [runningId, setRunningId] = useState<string | null>(null);

  async function investigate() {
    setBusy(true);
    setError(null);
    try {
      const link = asLink(text);
      setRunningId(await startInvestigation(image ? { image } : link ? { url: link } : { text }));
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

      {runningId ? (
        <ProgressChecklist
          id={runningId}
          onDone={(done) => {
            setRunningId(null);
            setResult(done);
          }}
          onFailed={(message) => {
            setRunningId(null);
            setError(message);
          }}
        />
      ) : result ? (
        <ResultView
          result={result}
          onReset={() => {
            setResult(null);
            setText("");
            setImage(null);
          }}
        />
      ) : (
        <>
          <PasteBox
            value={text}
            onChange={setText}
            image={image}
            onImage={setImage}
            onSubmit={investigate}
            busy={busy}
          />
          {error && <p className="message">{error}</p>}
        </>
      )}
    </main>
  );
}
