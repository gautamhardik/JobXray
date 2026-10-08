---
doc: scope
status: approved
---

# JobXray

An AI investigation agent that reads the recruiter messages you received, spots the scam funnel, checks the claimed internship against the company's official site, and tells you what to do before you pay or share anything. Tagline: X-ray the job before you apply.

## The Unique Kernel
Funnel plus evidence. Real company, real job title, and a real-looking LinkedIn post can still be a scam, so the agent reads the sequence (opportunity, recruiter contact, move from private chat to a group, group orientation or call, training pitch, payment request) and also tries to verify the claimed internship against the company's official web presence. The sequence is an investigative signal, not proof of fraud; WhatsApp or group recruiting alone is not a red flag. It does not output a bare "scam %"; it shows why and what to do next. The agent then genuinely challenges its own assessment: it turns the weak points of its first verdict into specific counter-hypotheses (for example, "could this be an authorized recruiting partner?") and runs a second, targeted search. If credible contradicting evidence appears, the verdict is revised and the report explains why; if none appears, it says so. Findings are kept clearly apart as fact, verified, unverified, unknown, contradiction, and assessment, and missing evidence is never treated as proof of fraud, so the tool never claims to "know" a job is a scam.

## Who It's For
The learner: a student who browses LinkedIn for internships and keeps meeting outdated or fake posts. They have been through the funnel: join a WhatsApp group or community, a group video call with other students, a sales pitch, then a fee. Today they lose hours finding out; the red flag they trust most (WhatsApp group first) is a hunch, not a check.

## The Core Loop
Paste the recruiter/job messages received. The agent extracts the company and role, flags the funnel steps and any payment request, looks up the company's official web presence (prioritizing its careers or jobs pages), compares the claim to what it finds, challenges its own assessment, and returns a risk level with evidence and a next step. More messages can be added to update the same investigation during the session.

## Inspiration & Identity
Name: JobXray, "X-ray this opportunity": the job looks normal on the surface and the scan shows what is underneath. Investigative, calm, trustworthy, serious: "Perplexity meets an investigative analyst," not a police or scam-detector dashboard and not a generic AI chat app. The user is already anxious, so the UI reduces uncertainty instead of amplifying fear. Warm off-white background, near-black type, thin borders, lots of whitespace, monospace for evidence and source details, red/orange only for real risk findings, green only for verified facts, subtle investigation animations, no neon, no big percentage gauge. One central screen: headline "Before you apply, investigate the opportunity," a paste box and an Investigate button; after investigating, the same screen becomes the report. Philosophy: "Don't tell me whether it feels fake. Show me why I should, or shouldn't, trust it." Detail goes to `3-prd`.

## Why This Matters to the Learner
"I want to get protected or safe... save my time from outdated job posts, fake job postings." They were a victim of fake internship offers and lost a lot of time.

## What "Working" Looks Like
Paste a suspicious recruiter conversation (WhatsApp group, group orientation, paid training, a ₹1,999 fee). The app shows the extracted company and role, the funnel steps it recognized, and one real live check of the company's official web presence. It reports the claimed internship could not be independently verified, shows the agent looking for evidence that could prove it wrong, and ends with a clear risk level (for example Critical Risk), the reasons, and a plain action (Proceed, Verify First, or Stop, for example "do not pay; verify directly with the company's official recruitment channel"), with the evidence viewable. If the challenge step finds something, the "before and after" revision is shown. This runs in about a minute on screen.

## The POC Boundary
- Input: pasted recruiter and job messages, a link to a job posting (JobXray fetches the page), or a screenshot (a vision model transcribes it). Added during the build at the learner's request.
- Funnel detection as a sequence (opportunity, recruiter contact, private-to-group migration, group orientation or call, training pitch, payment request), reported as e.g. "5 of 6 recruitment-funnel stages detected," with the concerning stages classified separately, plus red flags (rules plus AI reasoning).
- Company and role extraction.
- One real web verification: try to verify the claimed opportunity against the company's official web presence, prioritizing careers/jobs pages (discovering them, not assuming one URL), fetched with Scrapling.
- Safety rule: never infer fraud solely from absence. "Could not be independently verified" is combined with other signals (payment request, funnel, domain or recruiter mismatch, contradictions) to reach an assessment.
- An evidence ledger holds every claim, source, source reliability (official, first-party, user-provided, third-party, unknown), observation, status and live/cached flag; conclusions are reasoned from it, so the AI reasons over evidence and does not invent it.
- Cross-check of claim vs. evidence, then a real self-challenge: counter-hypotheses drawn from the first assessment's weak points (alternate official source, authorized intermediary, same job under another title, innocent explanation for the red flag, directly contradicting evidence) and a second targeted search.
- Findings labeled fact / verified / unverified / unknown / contradiction / assessment. Unknown means it could not be established at all; unverified means official sources were checked and did not confirm it.
- Output: risk level, evidence, explanation, and an action: Proceed / Verify First / Stop.
- If the live web check fails, fall back to stored evidence clearly labeled as cached, never presented as live. A saved sample case is acceptable for the demo fallback.
- Session state in memory only.

## Later
- LinkedIn-specific ingestion (pages behind a login)
- Multiple job boards and other sources
- Persistent case history
- Recruiter identity checks
- Browser automation, accounts, notifications

## Explicitly Cut
- Custom ML model: unnecessary; rules plus reasoning plus evidence suffices.
- Large RAG knowledge base: too much build time for a proof of concept.
- 20+ site integrations and full social-media crawling: fragile in a live demo.
- Database-heavy case management: not needed to prove the idea.
- Automated reporting to authorities, mobile app, job-board aggregation: out of scope.
