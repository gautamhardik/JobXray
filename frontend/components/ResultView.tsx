// Result view: spec.md > Components > Frontend > components/ResultView.tsx.
// The decision and its strongest evidence come first; the detail sits underneath.

import EvidenceRecord from "@/components/EvidenceRecord";
import type { EvidenceStatus, InvestigationResult } from "@/lib/api";

type Props = {
  result: InvestigationResult;
  onReset: () => void;
};

const GROUPS: { status: EvidenceStatus; title: string }[] = [
  { status: "contradiction", title: "Contradictions" },
  { status: "verified", title: "Verified" },
  { status: "unverified", title: "Unverified" },
  { status: "unknown", title: "Unknown" },
  { status: "fact", title: "Facts from what you provided" },
];

export default function ResultView({ result, onReset }: Props) {
  const top = result.top_evidence
    .map((id) => result.evidence.find((r) => r.id === id))
    .filter((r) => r !== undefined);

  return (
    <section aria-live="polite">
      <div className={`result decision-${result.decision.replace(" ", "-").toLowerCase()}`}>
        <div className="decision">{result.decision}</div>
        <div className="severity">{result.severity}</div>
        <p className="next-step">{result.next_step}</p>
      </div>

      <h2 className="section-title">Why</h2>
      <div className="evidence-list">
        {top.map((record) => (
          <EvidenceRecord key={record.id} record={record} />
        ))}
      </div>

      <details className="detail">
        <summary>
          {result.funnel.detected} of {result.funnel.total} recruitment-funnel stages detected
        </summary>
        {result.funnel.stages.length === 0 ? (
          <p className="muted">No recruitment-funnel stages appear in the text.</p>
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
        <p className="muted small">The sequence is an investigative signal, not proof of fraud.</p>
      </details>

      {GROUPS.map(({ status, title }) => {
        const records = result.evidence.filter((r) => r.status === status);
        if (records.length === 0) return null;
        return (
          <details className="detail" key={status}>
            <summary>
              {title} ({records.length})
            </summary>
            <div className="evidence-list">
              {records.map((record) => (
                <EvidenceRecord key={record.id} record={record} />
              ))}
            </div>
          </details>
        );
      })}

      <details className="detail">
        <summary>Reasoning</summary>
        <p>{result.rule}</p>
        <p className="muted small">
          The decision comes from fixed rules applied to the evidence above, not from the model&apos;s opinion.
          {result.dropped_quotes > 0 &&
            ` ${result.dropped_quotes} quoted passage${result.dropped_quotes === 1 ? " was" : "s were"} discarded because ${result.dropped_quotes === 1 ? "it was" : "they were"} not in your text.`}
        </p>
      </details>

      <div className="result-actions">
        <button type="button" className="link" onClick={onReset}>
          Start a new investigation
        </button>
      </div>
    </section>
  );
}
