"use client";

// spec.md > Components > Frontend > components/PasteBox.tsx.
// One box for everything: pasted text, a link, or up to three pasted or dropped screenshots.

import { useEffect, useState } from "react";

export const MAX_INPUT_CHARS = 10_000;
export const MAX_IMAGE_BYTES = 4 * 1024 * 1024;
export const MAX_SCREENSHOTS = 3;
const SENT_AS_IS = ["image/png", "image/jpeg", "image/webp"];
const MAX_SIDE = 2400;

// Sites where people find job posts. A short share message pointing at one of them
// ("Check out this job at Vidyalai: https://...") is investigated as that link.
const JOB_SITES =
  /(^|\.)(linkedin\.com|lnkd\.in|naukri\.com|internshala\.com|indeed\.com|glassdoor\.(com|co\.in)|foundit\.in|unstop\.com|wellfound\.com)$/i;
const URL_IN_TEXT = /(https?:\/\/|www\.)[^\s<>"')\]]+/gi;
const BARE_DOMAIN = /^(www\.)?[a-z0-9-]+(\.[a-z0-9-]+)+(\/\S*)?$/i;

function withScheme(url: string): string {
  return /^https?:\/\//i.test(url) ? url : `https://${url}`;
}

// A box holding only a link (with or without https://) is investigated as a link (slice 5).
export function asLink(value: string): string | null {
  const trimmed = value.trim();
  if (/^https?:\/\/\S+$/i.test(trimmed)) return trimmed;
  if (BARE_DOMAIN.test(trimmed) && !trimmed.includes("@")) return withScheme(trimmed);
  const urls = trimmed.match(URL_IN_TEXT) ?? [];
  if (trimmed.length <= 300 && urls.length === 1) {
    const url = withScheme(urls[0].replace(/[.,;:!?]+$/, ""));
    try {
      if (JOB_SITES.test(new URL(url).hostname)) return url;
    } catch {
      return null;
    }
  }
  return null;
}

// Re-encode screenshots the server can't take (GIF, BMP, AVIF, or over 4 MB) as JPEG.
async function normalise(file: File): Promise<string> {
  const original = await new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(new Error("read"));
    reader.readAsDataURL(file);
  });
  if (SENT_AS_IS.includes(file.type) && file.size <= MAX_IMAGE_BYTES) return original;

  const img = await new Promise<HTMLImageElement>((resolve, reject) => {
    const el = new Image();
    el.onload = () => resolve(el);
    el.onerror = () => reject(new Error("decode"));
    el.src = original;
  });
  let scale = Math.min(1, MAX_SIDE / Math.max(img.naturalWidth, img.naturalHeight));
  for (let attempt = 0; attempt < 5; attempt++) {
    const canvas = document.createElement("canvas");
    canvas.width = Math.max(1, Math.round(img.naturalWidth * scale));
    canvas.height = Math.max(1, Math.round(img.naturalHeight * scale));
    const context = canvas.getContext("2d");
    if (!context) throw new Error("canvas");
    context.fillStyle = "#ffffff";
    context.fillRect(0, 0, canvas.width, canvas.height);
    context.drawImage(img, 0, 0, canvas.width, canvas.height);
    const jpeg = canvas.toDataURL("image/jpeg", 0.88);
    if ((jpeg.length * 3) / 4 <= MAX_IMAGE_BYTES) return jpeg;
    scale *= 0.75;
  }
  throw new Error("size");
}

type Props = {
  value: string;
  onChange: (value: string) => void;
  images: string[];
  onImages: (dataUrls: string[]) => void;
  onSubmit: () => void;
  busy: boolean;
};

export default function PasteBox({
  value,
  onChange,
  images,
  onImages,
  onSubmit,
  busy,
}: Props) {
  const [imageError, setImageError] = useState<string | null>(null);
  const over = value.length > MAX_INPUT_CHARS;
  const canSubmit =
    (images.length > 0 || value.trim().length > 0) && !over && !busy;

  async function takeFiles(files: File[]): Promise<boolean> {
    const pictures = files.filter((f) => f.type.startsWith("image/"));
    if (pictures.length === 0) {
      if (files.length === 0) return false;
      setImageError(
        "Only screenshots can be added. For a PDF or document (like an offer letter), take a screenshot of it or paste its text.",
      );
      return true;
    }
    const room = MAX_SCREENSHOTS - images.length;
    if (room <= 0) {
      setImageError(`Add at most ${MAX_SCREENSHOTS} screenshots at a time.`);
      return true;
    }
    const added: string[] = [];
    for (const file of pictures.slice(0, room)) {
      try {
        added.push(await normalise(file));
      } catch {
        setImageError(
          "That image couldn't be opened. Take a PNG or JPEG screenshot instead.",
        );
        return true;
      }
    }
    setImageError(
      pictures.length > room
        ? `Only the first ${MAX_SCREENSHOTS} screenshots were added.`
        : null,
    );
    onImages([...images, ...added]);
    return true;
  }

  // With screenshots attached the main box is hidden, so the page takes the next pasted image.
  useEffect(() => {
    if (images.length === 0) return;
    const onPaste = (event: ClipboardEvent) => {
      const files = Array.from(event.clipboardData?.files ?? []);
      if (files.length > 0) {
        event.preventDefault();
        void takeFiles(files);
      }
    };
    window.addEventListener("paste", onPaste);
    return () => window.removeEventListener("paste", onPaste);
  });

  const link = asLink(value);

  return (
    <form
      className="reveal reveal-2"
      onSubmit={(event) => {
        event.preventDefault();
        if (canSubmit) onSubmit();
      }}
    >
      <label htmlFor="messages" className="tagline">
        Paste the recruiter or job messages you received, a link to the job
        posting, or a screenshot.
      </label>

      {images.length > 0 ? (
        <div
          className="image-preview"
          onDragOver={(event) => event.preventDefault()}
          onDrop={(event) => {
            event.preventDefault();
            void takeFiles(Array.from(event.dataTransfer.files));
          }}
        >
          <div className="image-strip">
            {images.map((src, index) => (
              <figure key={index}>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={src} alt={`Screenshot ${index + 1} to investigate`} />
                <button
                  type="button"
                  className="link"
                  onClick={() => onImages(images.filter((_, i) => i !== index))}
                >
                  Remove
                </button>
              </figure>
            ))}
          </div>
          {images.length < MAX_SCREENSHOTS && (
            <p className="muted small">
              Paste or drop another screenshot of the same chat or post (up to{" "}
              {MAX_SCREENSHOTS}).
            </p>
          )}
          <textarea
            className="added-text"
            aria-label="Other messages you received (optional)"
            value={value}
            onChange={(event) => onChange(event.target.value)}
            placeholder="Optional: paste any other messages you received with it"
          />
        </div>
      ) : (
        <div className={value.trim() ? "input-frame has-text" : "input-frame"}>
          <span className="input-scan" aria-hidden="true" />
          <textarea
            id="messages"
            value={value}
            onChange={(event) => onChange(event.target.value)}
            onPaste={(event) => {
              const files = Array.from(event.clipboardData.files);
              if (files.length > 0) {
                event.preventDefault();
                void takeFiles(files);
              }
            }}
            onDragOver={(event) => event.preventDefault()}
            onDrop={(event) => {
              const files = Array.from(event.dataTransfer.files);
              if (files.length > 0) {
                event.preventDefault();
                void takeFiles(files);
              }
            }}
            placeholder="Paste the recruiter or job messages, a job posting link, or a screenshot here…"
          />
        </div>
      )}

      <div className="paste-footer">
        <span className={over && images.length === 0 ? "counter over" : "counter"}>
          {images.length > 0
            ? `${images.length} screenshot${images.length > 1 ? "s" : ""} attached: JobXray will transcribe ${images.length > 1 ? "them" : "it"} first`
            : link
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
