"use client";

// spec.md > Components > Frontend > components/PasteBox.tsx.
// One box for everything: pasted text, a link, or a pasted or dropped screenshot.

import { useState } from "react";

export const MAX_INPUT_CHARS = 10_000;
export const MAX_IMAGE_BYTES = 4 * 1024 * 1024;
const IMAGE_TYPES = ["image/png", "image/jpeg", "image/webp"];

// A box holding only a link is investigated as a link (slice 5).
export function asLink(value: string): string | null {
  const trimmed = value.trim();
  return /^https?:\/\/\S+$/i.test(trimmed) ? trimmed : null;
}

type Props = {
  value: string;
  onChange: (value: string) => void;
  image: string | null;
  onImage: (dataUrl: string | null) => void;
  onSubmit: () => void;
  busy: boolean;
};

export default function PasteBox({ value, onChange, image, onImage, onSubmit, busy }: Props) {
  const [imageError, setImageError] = useState<string | null>(null);
  const over = value.length > MAX_INPUT_CHARS;
  const canSubmit = (image !== null || (value.trim().length > 0 && !over)) && !busy;

  function takeFile(file: File | undefined | null): boolean {
    if (!file || !file.type.startsWith("image/")) return false;
    if (!IMAGE_TYPES.includes(file.type)) {
      setImageError("Only PNG, JPEG, or WebP screenshots can be investigated.");
      return true;
    }
    if (file.size > MAX_IMAGE_BYTES) {
      setImageError("That screenshot is larger than 4 MB. Crop it or take a smaller one.");
      return true;
    }
    const reader = new FileReader();
    reader.onload = () => {
      setImageError(null);
      onImage(String(reader.result));
    };
    reader.readAsDataURL(file);
    return true;
  }

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        if (canSubmit) onSubmit();
      }}
    >
      <label htmlFor="messages" className="tagline">
        Paste the recruiter or job messages you received, a link to the job posting, or a screenshot.
      </label>

      {image ? (
        <div className="image-preview">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={image} alt="Screenshot to investigate" />
          <button type="button" className="link" onClick={() => onImage(null)}>
            Remove screenshot
          </button>
        </div>
      ) : (
        <textarea
          id="messages"
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onPaste={(event) => {
            const file = Array.from(event.clipboardData.files)[0];
            if (takeFile(file)) event.preventDefault();
          }}
          onDragOver={(event) => event.preventDefault()}
          onDrop={(event) => {
            const file = event.dataTransfer.files[0];
            if (takeFile(file)) event.preventDefault();
          }}
          placeholder="Paste the recruiter or job messages, a job posting link, or a screenshot here…"
        />
      )}

      <div className="paste-footer">
        <span className={over && !image ? "counter over" : "counter"}>
          {image
            ? "Screenshot attached: JobXray will transcribe it first"
            : asLink(value)
              ? "Link detected: JobXray will read this page"
              : `${value.length.toLocaleString()} / ${MAX_INPUT_CHARS.toLocaleString()}`}
        </span>
        <button type="submit" className="primary" disabled={!canSubmit}>
          {busy ? "Investigating…" : "Investigate"}
        </button>
      </div>
      {imageError && <p className="message">{imageError}</p>}
    </form>
  );
}
