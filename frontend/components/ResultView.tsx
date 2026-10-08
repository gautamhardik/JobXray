// Result view: spec.md > Components > Frontend > components/ResultView.tsx.
// Slice 2 shows extraction and the funnel; the decision is still a placeholder.

import type { InvestigationResult } from "@/lib/api";

type Props = {
  result: InvestigationResult;
  onReset: () => void;
};

export default function ResultView({ result, onReset }: Props) {
  return (
    <section className="result" aria-live="polite">
      <div className="decision">{result.decision}</div>
      <div className="severity">{result.severity}</div>

      <dl className="facts">
        <dt>Company</dt>
        <dd>{result.company ?? <span className="unknown">Unknown — not named in the text</span>}</dd>
        <dt>Role</dt>
        <dd>{result.role ?? <span className="unknown">Unknown — not named in the text</span>}</dd>
      </dl>

      <h2 className="section-title">
        {result.funnel.detected} of {result.funnel.total} recruitment-funnel stages detected
      </h2>
      {result.funnel.stages.length === 0 ? (
        <p className="muted">No recruitment-funnel stages appear in the pasted text.</p>
      ) : (
        <ol className="funnel">
          {result.funnel.stages.map((stage) => (
            <li key={stage.stage}>
              <div className="stage-label">{stage.label}</div>
              <blockquote className="excerpt">“{stage.excerpt}”</blockquote>
            </li>
          ))}
        </ol>
      )}
      <p className="muted small">
        The sequence is an investigative signal, not proof of fraud.
        {result.dropped_quotes > 0 &&
          ` ${result.dropped_quotes} quoted passage${result.dropped_quotes === 1 ? " was" : "s were"} discarded because ${result.dropped_quotes === 1 ? "it was" : "they were"} not in your text.`}
      </p>

      <div className="result-actions">
        <button type="button" className="link" onClick={onReset}>
          Start a new investigation
        </button>
      </div>
    </section>
  );
}
