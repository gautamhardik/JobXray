---
doc: prd
status: approved
---

# JobXray — Product Requirements

JobXray is a text-only investigation tool for people who have received a suspicious job or internship offer. The user pastes the recruiter messages or job details they received. JobXray investigates the opportunity, checks the claims against the company's official web presence, and tells the user whether to Proceed, Verify First, or Stop, with the evidence behind that answer.

Source: `scope.md > The Unique Kernel`, `scope.md > The Core Loop`, `scope.md > What "Working" Looks Like`, `scope.md > The POC Boundary`.

## The Core Journey

1. The user opens JobXray. They see the JobXray name, one paste box, and one "Investigate" button. Nothing else is on the first screen.
2. The user pastes the recruiter messages, job details, or conversation they received into the box.
3. The user clicks "Investigate." The screen changes into a live investigation view. It shows the steps JobXray is taking and which ones are done.
4. JobXray finishes and shows a single result. The top of the result says what the user should do: Proceed, Verify First, or Stop. Directly below that are the 2–3 strongest pieces of evidence behind the decision.
5. Underneath, the user can inspect the detail: the facts, the official-source checks, the self-challenge, and the reasoning.
6. Success: the user can answer three questions without trusting an unexplained score. What happened? What evidence supports it? What should I do now?

## Screens and Layout

- **Investigate screen (first open).** JobXray name at the top. One paste box. One "Investigate" button. No dashboard, no history, no account prompt.
- **Investigation view.** Replaces the paste screen in the same workspace. Shows the investigation steps as a checklist. Completed steps are checked; the current step is active.
- **Result view.** Same workspace. The decision and the top evidence sit at the top. Sections for facts, official-source checks, self-challenge, reasoning, and recommended action sit below and can be expanded.

Moving between views is one-way for a single investigation. A new investigation starts from the first screen.

## Look and Feel

Carried from `scope.md > Inspiration & Identity`. The learner has not yet confirmed these details in their own words; they are listed here so the spec and build have a starting point. Confirm at review.

- Calm, serious, investigative. Not a police or scam-alert dashboard; not a generic AI chat app.
- Warm neutral background, strong typography, generous whitespace, thin borders.
- No neon, no gradients, no large percentage gauge, no flashy AI effects.
- Motion only during an active investigation, and only to express the X-ray metaphor: a subtle scan effect when the investigation starts and scan or progress motion tied to the investigation steps. No 3D scene, shader background, or persistent animation. The result and evidence views stay calm and static. (Learner choice during build, "Option 2 — Mix".)
- Color is used only for meaning: red or orange for real risk findings, green for verified facts.
- Monospace for source and evidence details.

## Features and Behavior

### Investigating an opportunity

- The user pastes any amount of text. A full conversation is accepted, not just one message.
- Before any official-web check, JobXray identifies the company and establishes its legitimate official domain. A domain supplied in the job material (for example `xyz-careers-example.com`) cannot establish legitimacy, so it is never treated as the official source.
- JobXray identifies the company and the role from the pasted text. If either is missing, it says so and shows it as unknown.
- JobXray reads the pasted text as a sequence and reports which recruitment-funnel stages appear: opportunity, recruiter contact, move from private chat to a group, group orientation or call, training pitch, payment request. It reports the count (for example, "5 of 6 recruitment-funnel stages detected") and shows the relevant excerpt from the submitted text for each stage, not large portions of the conversation.
- The sequence is an investigative signal, not proof of fraud. WhatsApp or group recruiting alone is not treated as a red flag.
- JobXray then checks the company's official web presence, starting with careers or jobs pages, discovered from the official domain. It does not assume one URL structure. It fetches pages with Scrapling and records each page it checked.
- A missing vacancy is never treated as proof of fraud by itself. It is combined with other signals before it affects the decision.

### Evidence

- Every finding is one of: **Fact** (stated in the pasted text), **Verified** (confirmed by a reliable source), **Unverified** (official sources were checked and did not confirm it), **Unknown** (could not be established at all), **Contradiction** (two sources disagree), or **Assessment** (JobXray's interpretation).
- Every finding links to its source: the relevant excerpt of the pasted text, or the official page with its URL and the time it was checked.
- Each source has a reliability label: Official, First-party, User-provided, Third-party, or Unknown.
- Each source is marked Live (fetched during this investigation) or Cached (from a stored sample).

### Self-challenge

- Self-challenge runs on every investigation, including when the first assessment is Proceed. It is proportional: a short challenge for low-risk cases, a deeper targeted challenge for high-risk cases.
- After the first assessment, JobXray lists the weak points in its own reasoning and turns each into a specific counter-hypothesis. Examples: "Could the recruiter be an authorized partner?" "Could the role be listed under another title?" "Could the fee be for an optional external service?"
- For each counter-hypothesis, JobXray runs a targeted search and records what it found, or that it found nothing.
- If the self-challenge materially changes the assessment, the revised decision appears on the main answer, with a note underneath: "Assessment changed after contradictory evidence was found."
- If nothing changes the assessment, the result says so: "No credible contradictory evidence found."

### Result and recommendation

- The top of the result is one decision: **Proceed**, **Verify First**, or **Stop**, with one plain-language next step.
- Directly beneath the decision, a qualitative severity label, for example "STOP · Critical concern" or "VERIFY FIRST · Significant uncertainty". No percentages, no numerical scores.
- The severity label is kept separate from the decision because two cases can both need verification for different reasons.
- Directly below the decision: the 2–3 strongest pieces of evidence that led to it.
- Underneath: all facts, verified items, unverified items, unknowns, contradictions, the self-challenge, and the reasoning.

## States and Boundaries

- **First use** — The paste box is empty. The "Investigate" button does not start an investigation until there is text in the box.
- **Core principle** — JobXray never manufactures certainty from missing evidence. Unreachable sites, missing vacancies, and unknown facts are reported as what they are, never as proof.
- **Official site unreachable** — The result says the official source could not be reached. That check is marked Unknown or Unverified. A failed fetch is not a risk signal. The decision is based only on evidence actually obtained. If the missing verification matters, the default decision is **Verify First**, with the note: "We could not independently verify the opportunity because the official site was unreachable."
- **Nothing found on official pages** — Marked Unverified, not fraud. The decision depends on the other signals.
- **Unestablished official domain** — If no legitimate official domain can be established, the official-source check is marked Unknown, and the decision defaults to Verify First, with the note that the official source could not be established.
- **Input cannot be read** — (Assumption) The result says what could not be read and does not guess.
- **Cached demo** — If live checks fail during a demo, JobXray may show a stored sample investigation. It is labeled as Cached everywhere it appears. It is never presented as live.
- **Persistence** — Nothing is saved. The investigation lives in the session. Closing or refreshing the page starts over. No account, no history.

## Product Decisions

- The first screen has only the JobXray identity, one paste box, and one "Investigate" button — the learner's choice, to keep the first experience uncluttered.
- The result leads with the decision (Proceed / Verify First / Stop) and the 2–3 strongest evidence points. Detail sits underneath — learner's choice, so the user can answer "what happened, what supports it, what do I do" at a glance.
- If the self-challenge changes the assessment, the change appears on the main answer with a note — learner's choice, because the transparency is part of what makes the tool trustworthy.
- A failed official-site check is not a risk signal; the default is Verify First with a note — learner's choice.
- A missing vacancy or a missing official source is never proof of fraud on its own — learner's choice, carried from the approved scope.
- The sequence is an investigative signal, not proof of fraud — learner's choice, carried from the approved scope.
- Self-challenge runs on every investigation, proportional to risk — learner's choice.
- Severity is shown qualitatively under the decision (for example "STOP · Critical concern"), with no percentages or scam scores — learner's choice.
- The official domain is established before any official-source check; a domain supplied in the job material cannot establish legitimacy — learner's choice.
- Excerpts, not large quotes, from the submitted conversation — learner's choice.
- JobXray never manufactures certainty from missing evidence — learner's choice, a core product principle.

## What We're Building

- Paste-only input (text of recruiter messages, job details, or a conversation).
- The first screen as described above.
- Live investigation view with checklist-style progress.
- Company and role extraction, with unknowns shown.
- Funnel recognition, reported as a count with quoted evidence.
- One real official-web check (careers or jobs pages), fetched with Scrapling, with each page recorded.
- Evidence labels (Fact / Verified / Unverified / Unknown / Contradiction / Assessment) and source reliability labels.
- Self-challenge on every investigation, proportional to risk, with counter-hypotheses, targeted searches, and the revision rule.
- Official domain establishment before official-source checks.
- Result view: decision, qualitative severity, top evidence, and expandable detail.
- One cached sample investigation for the demo, clearly labeled.
- Session-only state.

## Deferred From the POC

- Screenshot and image input — needs OCR and handling of bad images.
- Job URL input and direct page scraping by the user — the agent finds pages itself.
- LinkedIn input or automation — LinkedIn blocks automated access; not a dependency.
- Investigation history, saved cases, accounts — not needed to prove the idea.
- Multiple job boards and social-media sources — fragile in a live demo.
- Recruiter identity checks beyond the official web presence.

## Possible Later Enhancements

- Screenshot input with OCR.
- Export of the report as a file.
- More official sources per company.

## Non-Goals

- Telling the user whether a job is a scam. JobXray reports evidence and a recommended action.
- Reporting anyone to authorities.
- Training a custom model.
- A mobile app.
- Showing a percentage or "scam score."

## Open Questions

- **Resolved:** Self-challenge runs on every investigation, proportional to risk.
- **Resolved:** Unreachable official site defaults to Verify First, not Proceed.
- **Resolved:** Severity appears beneath the decision as a qualitative label, not a risk level on its own.
- **Can wait for build:** Exact wording of the progress steps and the decision labels.
- **Can wait for build:** Which stored sample case to use for the demo fallback.
