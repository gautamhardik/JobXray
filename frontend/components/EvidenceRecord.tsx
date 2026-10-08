// One evidence record: spec.md > Components > Frontend > components/EvidenceRecord.tsx.

import type { EvidenceRecord as Record } from "@/lib/api";

const STATUS_LABEL: { [key in Record["status"]]: string } = {
  fact: "Fact",
  verified: "Verified",
  unverified: "Unverified",
  unknown: "Unknown",
  contradiction: "Contradiction",
};

const SOURCE_LABEL: { [key: string]: string } = {
  pasted_text: "Your pasted text",
  linked_page: "The page you linked",
  screenshot: "Your screenshot",
  official_page: "Official company page",
  none: "No source checked",
};

export default function EvidenceRecord({ record }: { record: Record }) {
  return (
    <article className="evidence">
      <div className="evidence-head">
        <span className={`badge badge-${record.status}`}>{STATUS_LABEL[record.status]}</span>
        <span className="evidence-claim">{record.claim}</span>
      </div>
      {record.excerpt && <blockquote className="excerpt">“{record.excerpt}”</blockquote>}
      <p className="evidence-observation">{record.observation}</p>
      <p className="evidence-meta">
        {record.source_url ? (
          <a href={record.source_url} target="_blank" rel="noreferrer noopener">
            {record.source_url}
          </a>
        ) : (
          SOURCE_LABEL[record.source_type] ?? record.source_type
        )}
        {" · "}
        {record.reliability}
        {" · "}
        {record.live_or_cached === "cached" ? "Cached example" : "Live"}
        {" · "}
        {record.id}
      </p>
    </article>
  );
}
