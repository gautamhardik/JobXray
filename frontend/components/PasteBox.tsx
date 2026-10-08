"use client";

// spec.md > Components > Frontend > components/PasteBox.tsx.

export const MAX_INPUT_CHARS = 10_000;

// A box holding only a link is investigated as a link (slice 5).
export function asLink(value: string): string | null {
  const trimmed = value.trim();
  return /^https?:\/\/\S+$/i.test(trimmed) ? trimmed : null;
}

type Props = {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  busy: boolean;
};

export default function PasteBox({ value, onChange, onSubmit, busy }: Props) {
  const over = value.length > MAX_INPUT_CHARS;
  const canSubmit = value.trim().length > 0 && !over && !busy;

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        if (canSubmit) onSubmit();
      }}
    >
      <label htmlFor="messages" className="tagline">
        Paste the recruiter or job messages you received, or a link to the job posting.
      </label>
      <textarea
        id="messages"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder="Paste the recruiter or job messages here…"
      />
      <div className="paste-footer">
        <span className={over ? "counter over" : "counter"}>
          {asLink(value)
            ? "Link detected: JobXray will read this page"
            : `${value.length.toLocaleString()} / ${MAX_INPUT_CHARS.toLocaleString()}`}
        </span>
        <button type="submit" className="primary" disabled={!canSubmit}>
          {busy ? "Investigating…" : "Investigate"}
        </button>
      </div>
    </form>
  );
}
