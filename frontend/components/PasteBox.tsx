"use client";

// spec.md > Components > Frontend > components/PasteBox.tsx.

export const MAX_INPUT_CHARS = 10_000;

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
        Paste the recruiter or job messages you received.
      </label>
      <textarea
        id="messages"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder="Paste the recruiter or job messages here…"
      />
      <div className="paste-footer">
        <span className={over ? "counter over" : "counter"}>
          {value.length.toLocaleString()} / {MAX_INPUT_CHARS.toLocaleString()}
        </span>
        <button type="submit" className="primary" disabled={!canSubmit}>
          {busy ? "Investigating…" : "Investigate"}
        </button>
      </div>
    </form>
  );
}
