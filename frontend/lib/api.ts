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

export type InvestigationInput = { text: string } | { url: string } | { image: string };

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
};

export async function startInvestigation(input: InvestigationInput): Promise<InvestigationResult> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}/api/investigations`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    });
  } catch {
    throw new Error("JobXray could not reach its investigation server. Check that it is running.");
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
