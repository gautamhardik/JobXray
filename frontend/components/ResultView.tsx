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
      {result.cached_at && (
        <p className="cached-banner">
          Example investigation: a real run saved on {new Date(result.cached_at).toLocaleDateString()}. Every record
          below is cached, not checked live today.
        </p>
      )}
      <div className={`result decision-${result.decision.replace(" ", "-").toLowerCase()}`}>
        <div className="decision">{result.decision}</div>
        <div className="severity">{result.severity}</div>
        <p className="next-step">{result.next_step}</p>
        {result.challenge.changed && (
          <p className="revision-note">
            {result.challenge.note} First assessment: {result.challenge.first_decision}.
          </p>
        )}
        {(result.notes ?? []).map((note) => (
          <p className="revision-note" key={note}>
            {note}
          </p>
        ))}
        {result.source.source_type === "linked_page" && result.source.source_url && (
          <p className="muted small">
            Read from:{" "}
            <a href={result.source.source_url} target="_blank" rel="noreferrer noopener">
              {result.source.source_url}
            </a>
          </p>
        )}
      </div>

      <h2 className="section-title">Why</h2>
      <div className="evidence-list">
        {top.map((record) => (
          <EvidenceRecord key={record.id} record={record} />
        ))}
      </div>

      {result.source.transcription && (
        <details className="detail">
          <summary>What JobXray read from your screenshot</summary>
          <pre className="transcription">{result.source.transcription}</pre>
          <p className="muted small">Every quoted excerpt was checked against this transcription.</p>
        </details>
      )}

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
        <summary>Self-challenge: {result.challenge.note}</summary>
        {result.challenge.hypotheses.length === 0 ? (
          <p className="muted">No counter-hypotheses were checked.</p>
        ) : (
          <ol className="hypotheses">
            {result.challenge.hypotheses.map((h, i) => (
              <li key={i}>
                <div className="stage-label">{h.question}</div>
                <p>{h.finding}</p>
                {h.checked_urls.length > 0 && (
                  <p className="evidence-meta">
                    Checked: {h.checked_urls.join(" · ")}
                  </p>
                )}
              </li>
            ))}
          </ol>
        )}
        <p className="muted small">
          JobXray looks for evidence that could prove its first assessment wrong, on the company&apos;s official
          site only. First assessment: {result.challenge.first_decision}.
        </p>
      </details>

      <details className="detail">
        <summary>Reasoning</summary>
        <p>{result.rule}</p>
        <p className="muted small">
          The decision comes from fixed rules applied to the evidence above, not from the model&apos;s opinion.
          {` ${result.model_calls} model call${result.model_calls === 1 ? "" : "s"}, ${result.fetches} page${result.fetches === 1 ? "" : "s"} read${result.searches ? `, ${result.searches} web search${result.searches === 1 ? "" : "es"}` : ""}.`}
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
