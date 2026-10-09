// The only file that calls the backend. spec.md > Components > Frontend > lib/api.ts.

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type FunnelStage = {
  stage: string;
  label: string;
  excerpt: string;
};

export type EvidenceStatus = "fact" | "verified" | "unverified" | "unknown" | "contradiction";

export type EvidenceRecord = {
  id: string;
  claim_id: string;
  claim: string;
  source_type: string;
  source_url: string | null;
  excerpt: string | null;
  reliability: string;
  observation: string;
  supports_or_contradicts: string;
  status: EvidenceStatus;
  live_or_cached: "live" | "cached";
  checked_at: string;
};

export type Decision = "STOP" | "VERIFY FIRST" | "PROCEED";

export type Origin = {
  source_type: "pasted_text" | "linked_page" | "screenshot";
  source_url: string | null;
  reliability: string;
  transcription: string | null;
};

export type CheckedHypothesis = {
  question: string;
  kind: string;
  checked_urls: string[];
  finding: string;
};

export type Challenge = {
  hypotheses: CheckedHypothesis[];
  changed: boolean;
  first_decision: string;
  note: string;
};

export type InvestigationInput = { text: string } | { url: string } | { images: string[]; text?: string };

export type InvestigationResult = {
  decision: Decision;
  severity: string;
  next_step: string;
  rule: string;
  summary: string;
  company: string | null;
  role: string | null;
  funnel: { detected: number; total: number; stages: FunnelStage[] };
  evidence: EvidenceRecord[];
  top_evidence: string[];
  dropped_quotes: number;
  model_calls: number;
  fetches: number;
  source: Origin;
  challenge: Challenge;
  cached_at: string | null;
  notes?: string[]; // limits of this run, e.g. a post that lists several offers
};

export type Step = {
  key: string;
  label: string;
  state: "pending" | "active" | "done" | "skipped";
  note: string | null;
};

export type InvestigationStatus = {
  id: string;
  status: "running" | "done" | "failed";
  steps: Step[];
  result: InvestigationResult | null;
  error: string | null;
};

const UNREACHABLE = "JobXray could not reach its investigation server. Check that it is running.";

export async function startInvestigation(input: InvestigationInput): Promise<string> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}/api/investigations`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    });
  } catch {
    throw new Error(UNREACHABLE);
  }
  if (!response.ok) {
    throw new Error(await readError(response));
  }
  return (await response.json()).id;
}

export async function getInvestigation(id: string): Promise<InvestigationStatus> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}/api/investigations/${encodeURIComponent(id)}`);
  } catch {
    throw new Error(UNREACHABLE);
  }
  if (!response.ok) {
    throw new Error(await readError(response));
  }
  return response.json();
}

export async function getExample(): Promise<InvestigationResult> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}/api/example`);
  } catch {
    throw new Error(UNREACHABLE);
  }
  if (!response.ok) {
    throw new Error(await readError(response));
  }
  return response.json();
}

async function readError(response: Response): Promise<string> {
  try {
    const body = await response.json();
    const detail = body?.detail;
    if (Array.isArray(detail) && detail[0]?.msg) {
      return String(detail[0].msg).replace(/^Value error, /, "");
    }
    if (typeof detail === "string") return detail;
  } catch {
    // fall through to the generic message
  }
  return "The investigation could not start. Try again.";
}
