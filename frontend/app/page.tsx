"use client";

// Investigation workspace: spec.md > Components > Frontend > app/page.tsx.

import { useState } from "react";

import PasteBox, { asLink } from "@/components/PasteBox";
import ProgressChecklist from "@/components/ProgressChecklist";
import ResultView from "@/components/ResultView";
import ScrambleText from "@/components/ScrambleText";
import XrayBackdrop from "@/components/XrayBackdrop";
import {
  getExample,
  startInvestigation,
  type InvestigationResult,
} from "@/lib/api";

export default function Home() {
  const [text, setText] = useState("");
  const [images, setImages] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<InvestigationResult | null>(null);
  const [runningId, setRunningId] = useState<string | null>(null);

  async function showExample() {
    setError(null);
    try {
      setResult(await getExample());
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "The example could not be loaded.",
      );
    }
  }

  async function investigate() {
    setBusy(true);
    setError(null);
    try {
      const link = asLink(text);
      setRunningId(
        await startInvestigation(
          images.length > 0 ? { images } : link ? { url: link } : { text },
        ),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  const phase = runningId ? "running" : result ? "result" : "input";

  return (
    <>
      <XrayBackdrop phase={phase} />
      <main className={`phase-${phase}`}>
        <header>
          <div className="brand">
            Job<span className="brand-x">X</span>ray
          </div>
          {phase === "input" ? (
            <h1 className="hero reveal">
              <ScrambleText text="X-ray" className="hero-x" /> the job before
              you apply.
            </h1>
          ) : (
            <div className="tagline">X-ray the job before you apply.</div>
          )}
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
              setImages([]);
            }}
          />
        ) : (
          <>
            <PasteBox
              value={text}
              onChange={setText}
              images={images}
              onImages={setImages}
              onSubmit={investigate}
              busy={busy}
            />
            {error && <p className="message">{error}</p>}
            <p className="example-line reveal reveal-3">
              Not sure what to paste?{" "}
              <button type="button" className="link" onClick={showExample}>
                Try an example
              </button>
            </p>
          </>
        )}
      </main>
    </>
  );
}
