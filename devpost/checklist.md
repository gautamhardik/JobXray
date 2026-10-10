---
doc: checklist
status: approved
---

# Build Checklist

Build mode: fast (switched from learn after slice 4 — the learner asked the agent to complete all remaining slices; hands-on review at the end)

## Slices

- [x] **1. You can paste text, press Investigate, and see a result from the backend**
  Becomes usable: The paste screen sends text to the FastAPI backend, which returns a fixed placeholder result that the result view shows. The whole path from browser to server and back works before any real analysis exists.
  Why now: Proves the frontend, backend, and their connection end to end, so every later slice lands on a working path. Bootstrapping (scaffolds, dependencies, config, git-ignored env file) happens here because it is needed for the first real behavior.
  PRD ref: `prd.md > Features and Behavior > Investigating an opportunity` (paste and submit), `prd.md > Screens and Layout`
  Spec ref: `spec.md > Components > Frontend` (`app/page.tsx`, `components/PasteBox.tsx`, `lib/api.ts`), `spec.md > Components > Backend` (`app/main.py`, `app/config.py`), `spec.md > File Structure`, `spec.md > Where It Runs and How Someone Tries It`
  Build: Scaffold `frontend/` (Next.js, TypeScript, App Router) and `backend/` (FastAPI, Uvicorn, Pydantic, `requirements.txt`, `.env.example`). Add the paste box with the 10,000-character limit and a disabled Investigate button until text is present. Add `POST /api/investigations` (validates length, returns a fixed result with a placeholder decision) and the frontend call through `lib/api.ts`. Show the result in a plain result view. Use the spec's palette variables in `globals.css`.
  Verify (mechanical): Start the backend (`uvicorn app.main:app --port 8000`) and the frontend (`npm run dev`). Run `curl -X POST localhost:8000/api/investigations` with a JSON body and confirm a JSON response. Submit text in the browser and confirm the placeholder result appears. Submit an empty paste and confirm the button stays disabled. Submit 10,001 characters through the API and confirm a 422 or 400 response with a message.
  Learner check: Open the app, paste any text, press Investigate, and say whether the first screen looks calm and clear, and whether the placeholder result appears where you expected.
  Commit: `Add paste screen and backend round trip`

- [x] **2. Pasted messages reveal their recruitment funnel, with the exact text behind each stage**
  Becomes usable: Pasting a recruiter conversation shows which funnel stages appear (for example "3 of 6 recruitment-funnel stages detected"), and each stage links to the excerpt that supports it. Quotes that are not in the pasted text are discarded.
  Why now: This is the product's kernel: the sequence, not a keyword, is the signal. It is also the first real model call (OpenRouter), so the model and key get checked here, while the rest of the build is still small.
  PRD ref: `prd.md > Features and Behavior > Investigating an opportunity` (company and role, funnel, excerpts), `prd.md > Features and Behavior > Evidence` (Fact status)
  Spec ref: `spec.md > Components > Backend > extract.py` (call 1), `spec.md > Components > Backend > llm_client.py`, `spec.md > Components > Backend > pipeline.py` (model-call budget), `spec.md > Stack > Reasoning`, `spec.md > Decisions and Open Issues > Open issues` (model ID)
  Build: Write `app/llm/llm_client.py` (the only model caller, through OpenRouter; requests strict JSON, validates it, counts calls against `MAX_MODEL_CALLS = 4`), `app/prompts/extract.md`, and `app/investigation/extract.py`. Extraction returns claims (company, role, stipend, fee, application link) and funnel stages, each with an excerpt. Code checks every excerpt is a substring of the pasted text; any failing excerpt is dropped and counted. Wire the result into the pipeline and the result view. Keep the placeholder decision for now.
  Verify (mechanical): Unit test `tests/test_quote_check.py`: an excerpt present in the text is kept, an altered excerpt is dropped. Run the fixture recruiter conversation through the backend and confirm the funnel stages and excerpts. Call the backend with the model call stubbed and confirm the call counter increments once per investigation. Confirm `backend/.env` is not listed by `git status`.
  Learner check: Paste a recruiter conversation (with the fee and the WhatsApp group) and say whether each funnel stage shown is the right one and whether its excerpt is really from your text.
  Commit: `Extract claims and funnel stages from pasted text`

- [x] **3. Stops and verify-firsts come from the evidence rules, not from a model verdict**
  Becomes usable: A pasted message with a payment request shows STOP with the payment fact as the top evidence. A message with no payment request and no official check shows VERIFY FIRST. The decision and its reasons are produced by code.
  Why now: The decision logic is the part most worth testing in isolation. Doing it before the web check means the rules are proven before real web evidence arrives.
  PRD ref: `prd.md > Features and Behavior > Evidence`, `prd.md > Features and Behavior > Result and recommendation`, `prd.md > States and Boundaries` (official site unreachable defaults to Verify First)
  Spec ref: `spec.md > Components > Backend > ledger.py`, `spec.md > Components > Backend > status.py`, `spec.md > Decisions and Open Issues > Derived implementation decisions`, `spec.md > Data Model`
  Build: Write `app/evidence/ledger.py` (the evidence record model with the fields from the spec) and `app/evidence/status.py` with pure functions: a payment request from the pasted text becomes a Fact (user-provided); a status function returns Fact, Verified, Contradiction, Unverified, or Unknown; a decision function returns STOP, VERIFY FIRST, or PROCEED with the severity label. Pipeline builds the evidence list from extraction output and sets the decision with these functions. The result view shows the decision, the severity label, and the top 2–3 evidence records. Write `tests/test_status_rules.py` covering each rule.
  Verify (mechanical): `pytest tests/test_status_rules.py` passes, with a case for each rule and the rule order from the spec. Run the fee message through the backend and confirm STOP · Critical concern with the fee fact as top evidence. Run a message with no fee and confirm VERIFY FIRST · Significant uncertainty, because the opportunity is Unknown without an official check.
  Learner check: Paste the fee message and then a message with no fee. For each, say whether the decision and its top evidence make sense to you, and what the app tells you to do next.
  Commit: `Decide STOP or VERIFY FIRST from evidence rules`

- [x] **4. A real company's official site is checked, and the result says what was verified and what could not be**
  Becomes usable: For a real company name in the pasted text, the backend proposes its official domain, checks the domain with several first-party signals, fetches the careers or jobs pages with Scrapling, and records what those pages do or do not say about the claimed role. Unreachable or unestablished sites show as Unknown, never as fake.
  Why now: This is the "real web investigation" that proves the agent checks claims rather than guessing from text. It depends on slices 2 and 3, which supply the claims and the rules.
  PRD ref: `prd.md > Features and Behavior > Investigating an opportunity` (official domain before checks, official web presence), `prd.md > Features and Behavior > Evidence` (Verified, Unverified, Unknown)
  Spec ref: `spec.md > Components > Backend > plan.py` (call 2 and domain check), `spec.md > Components > Backend > scraper.py`, `spec.md > Components > Backend > observe.py` (call 3), `spec.md > Stack > Web extraction`, `spec.md > External Services and Dependencies`, `spec.md > Decisions and Open Issues > Derived implementation decisions` (domain signals)
  Build: First confirm Scrapling's installed API (fetch call, text extraction) against its documentation and record the exact calls in `scraper.py`. Write `app/web/scraper.py` (fetch, extract text, record URL and time, count against `MAX_FETCHES = 8`). Write `app/investigation/plan.py` (call 2 proposes the domain and the questions) and the domain check: several first-party identity signals on the fetched site, never a company-name match alone. Discover careers or jobs pages linked from the verified domain. Write `app/investigation/observe.py` (call 3 returns observations with quoted passages; quotes not found in the fetched text are dropped). Feed results into `status.py` so Verified, Unverified, and Unknown follow the rules. An unfetchable page is Unknown, never Unverified.
  Verify (mechanical): Test with saved page fixtures: a page that lists the role (Verified), a page that does not (Unverified, only if the careers page was actually inspected), a blocked page (Unknown), and a look-alike domain with only a name match (domain Unknown). `pytest` for these cases. Run one real company through the backend and confirm the official domain, the pages fetched, and the quoted observations match what the pages say. Check the fetch count never exceeds 8.
  Learner check: Paste a message from a real company you know, with a role and a fee. Say whether the pages JobXray says it checked are really that company's official pages, and whether the verified or unknown label matches what you can see on the site yourself.
  Commit: `Check official company pages and record evidence`

- [x] **5. A link to a job posting is fetched and investigated like pasted text**
  Becomes usable: Pasting only a link (for example a job board posting) makes JobXray fetch that page, pull out its readable text, and run the same extraction, rules, and official-site check on it. Pages behind a login or blocked pages show "JobXray couldn't read this page. Paste the text instead."
  Why now: It reuses the Scrapling wrapper from slice 4, so it costs little once that exists, and it is the input the learner most wants.
  PRD ref: `prd.md > Features and Behavior > Investigating an opportunity` (link input), `prd.md > States and Boundaries` (input cannot be read)
  Spec ref: `spec.md > Components > Backend > app/input/link.py`, `spec.md > Components > Backend > scraper.py`, `spec.md > Components > Frontend > components/PasteBox.tsx`, `spec.md > Components > Backend > app/main.py`
  Build: Accept `url` in `POST /api/investigations` (exactly one of text, url, image). Write `app/input/link.py`: http/https only; resolve the host and refuse private, loopback, and link-local addresses; fetch with `scraper.py` (counts against `MAX_FETCHES`); cap the text at 10,000 characters; record the page as a user-provided source. `PasteBox.tsx` sends a box containing only a link as `url`. The result shows "Read from: <link>".
  Verify (mechanical): Tests: `http://127.0.0.1`, `http://localhost`, `http://10.0.0.5`, and `file:///` are refused before any fetch; a saved posting page fixture produces the same stages as its pasted text; a login-wall fixture produces the plain message. Live run: one real public job posting link returns a result, and one LinkedIn link returns either a result or the plain message, never a crash.
  Learner check: Paste a link to a real job posting you found online. Say whether JobXray read the right page and found the right company, role, and stages.
  Commit: `Investigate a job posting from its link`

- [x] **6. A screenshot is transcribed and investigated, and you can see the transcription**
  Becomes usable: Pasting or dropping a screenshot of a WhatsApp chat or offer letter into the box shows a small preview; investigating it shows the transcription the vision model read, then the usual result built from that transcription.
  Why now: Screenshots are how scam offers are usually shared; this slice adds them once the text path is fully proven, and it raises the model-call budget to 5 only for image investigations.
  PRD ref: `prd.md > Features and Behavior > Investigating an opportunity` (screenshot input, model-call budget), `prd.md > States and Boundaries` (input cannot be read)
  Spec ref: `spec.md > Components > Backend > app/input/image.py`, `spec.md > Components > Backend > app/config.py`, `spec.md > Components > Backend > llm_client.py`, `spec.md > Components > Frontend > components/PasteBox.tsx`
  Build: Accept `image` (data URL; PNG, JPEG, or WebP; at most 4 MB). Write `app/input/image.py` with one plain-text transcription call to `VISION_MODEL` (default `google/gemma-4-31b-it:free`) through `llm_client.py`, using `MAX_MODEL_CALLS_IMAGE = 5`. Show the transcription in the result. Excerpts are checked against the transcription. `PasteBox.tsx` handles paste and drop of an image, with a preview and a remove control.
  Verify (mechanical): Tests: oversized or non-image data is refused before any model call; the budget is 5 for image runs and 4 otherwise; an empty transcription gives the plain error. Live run: a generated screenshot of the fee conversation fixture produces a transcription and the payment-request stage.
  Learner check: Take a screenshot of a recruiter message (or any job offer image) and paste it into the box. Say whether the transcription matches the image and whether the result makes sense.
  Commit: `Investigate a screenshot through a visible transcription`

- [x] **7. The progress checklist shows each investigation step as it happens**
  Becomes usable: While an investigation runs, the screen shows the steps as a checklist (analyzing, identifying company and role, checking the recruitment sequence, establishing the official domain, checking official pages), with each step checked off as it finishes.
  Why now: Real web checks take seconds, and an empty screen during that time makes the app look broken. This is also the first place the investigation becomes visibly "work in progress."
  PRD ref: `prd.md > Screens and Layout` (investigation view), `prd.md > Features and Behavior > Investigating an opportunity`
  Spec ref: `spec.md > Components > Frontend > ProgressChecklist.tsx`, `spec.md > Components > Backend > pipeline.py` (step-status list), `spec.md > Data Model > Investigation`, `spec.md > Look and Feel` (subtle motion only)
  Build: The pipeline updates a step list on the in-memory investigation as each step starts and ends. `GET /api/investigations/{id}` returns the steps and, when finished, the result. `ProgressChecklist.tsx` polls every 1.5 seconds and stops when the status is done or failed. Replace the placeholder result view with the real result view, unchanged in layout from slice 3.
  Verify (mechanical): Start an investigation and poll the GET endpoint, confirming steps change from pending to active to done in order. Confirm polling stops when the investigation finishes. Confirm an unknown id returns 404.
  Learner check: Start an investigation and watch the checklist. Say whether each step name matches what you expected JobXray to be doing at that moment.
  Commit: `Show live investigation progress`

- [x] **8. The agent challenges its first verdict, and a changed verdict is shown on the main answer**
  Becomes usable: After the first assessment, JobXray writes specific counter-hypotheses, runs a targeted check, and re-applies the rules. If the result changes, the main answer shows the new decision with the note "Assessment changed after contradictory evidence was found." If it does not, the result says "No credible contradictory evidence found."
  Why now: Self-challenge is the feature the product's identity rests on. It needs the web check and the rules already working, so that a changed verdict is grounded in real evidence.
  PRD ref: `prd.md > Features and Behavior > Self-challenge`, `prd.md > Features and Behavior > Result and recommendation` (revision note)
  Spec ref: `spec.md > Components > Backend > challenge.py` (call 4), `spec.md > Decisions and Open Issues > Derived implementation decisions` (self-challenge changes the decision only through a Verified or Contradiction record), `spec.md > Components > Frontend > ResultView.tsx`
  Build: Write `app/prompts/challenge.md` and `app/investigation/challenge.py` (call 4 returns counter-hypotheses and targeted pages, within the fetch budget; code fetches them and re-runs the rules). Always run one challenge round, with a lighter challenge for low-risk first assessments and a deeper one for high-risk. Assemble the report text in code from evidence record IDs. Show the revision note on the main answer when the decision changes.
  Verify (mechanical): Tests for the revision logic: a challenge that finds a Verified record changes VERIFY FIRST to PROCEED; a challenge that finds nothing leaves the decision unchanged and shows the "no credible contradictory evidence" line; the report cites only record IDs that exist. Confirm the total model calls stay at 4 and total fetches at 8 in a run that triggers the challenge.
  Learner check: Run an investigation where the first result is cautious, and read the self-challenge section. Say whether the counter-hypotheses are the ones you would have asked yourself, and whether the final decision explains any change.
  Commit: `Challenge the first verdict and revise when evidence changes`

- [x] **9. The example investigation works without the internet, and failures show plain messages**
  Becomes usable: A "Try an example" option loads a saved investigation, clearly labeled Cached. When the model or the web fails, the person sees a plain message, never a guessed result.
  Why now: The demo recording and any judge's first click depend on this. It comes after the features it protects, so the saved case is a real run.
  PRD ref: `prd.md > States and Boundaries` (first use, cached demo, persistence, official site unreachable, input cannot be read), `prd.md > Screens and Layout` (example option)
  Spec ref: `spec.md > Components > Backend > cached_case.json`, `spec.md > Important Failure Modes`, `spec.md > Decisions and Open Issues > Open issues` (sample case choice)
  Build: Save one real investigation as `app/samples/cached_case.json` with every evidence record marked `cached`. Add "Try an example" to the paste screen, loading that case with a visible Cached label on every record and the result. Map model errors, timeouts, free-tier rate limits, and budget refusals to plain messages in the result view. Stop an investigation cleanly if the server restarts (frontend shows the interrupted message).
  Verify (mechanical): Load the example with the network disabled and confirm the full result appears with Cached labels. Make the API key invalid and confirm the plain error message appears and no partial result is shown. Run `pytest` for the full suite.
  Learner check: Turn off your internet, open the app, and load the example. Say whether the result still makes sense, and whether it is clearly labeled as an example.
  Commit: `Add cached example and plain failure messages`

- [x] **10. The app matches the approved look and feel, on a phone-width screen too**
  Becomes usable: The whole flow reads as calm, serious, and evidence-first, with no dashboard cards or flashing effects, and it works at phone width without horizontal scrolling.
  Why now: Visual polish comes last so it styles the real screens, not placeholders, and so judging of the look is done against the actual product.
  PRD ref: `prd.md > Look and Feel`, `prd.md > Screens and Layout`
  Spec ref: `spec.md > Look and Feel`, `spec.md > Components > Frontend > globals.css` (palette variables), `spec.md > Components > Frontend > EvidenceRecord.tsx` (monospace source details)
  Build: Apply the palette, typography, spacing, and thin borders across the three views. Use red or orange only for risk findings and green only for verified facts. Make the layout single-column at phone width with a 16px side gutter and no horizontal page scroll. Add the CSS scan-line motion when Investigate is pressed and in the progress view only, turned off under `prefers-reduced-motion`; the result and evidence views stay static.
  Verify (mechanical): Check the three views at desktop width and at 375px width in the browser; confirm no horizontal scroll and no text overflow. Confirm no gradients, shadows beyond thin borders, or percentage gauges are present in the CSS or markup.
  Learner check: Open the app on a laptop and on your phone (or a narrow window). Say whether it feels calm and serious, and whether any color or motion feels like it is trying too hard.
  Commit: `Apply calm investigative look and phone-width layout`

## Hands-on Checkpoints

<!-- Early feedback at the boundary after slice 3, when the kernel decision works end to end. Final kick-the-tires after slice 10. -->

- [x] Early usable behavior explored: after slice 3 — the learner chose to have the agent run the checks instead (7 composite scam messages, then fee and no-fee runs); learner feedback at this point was about scope (add link and screenshot input) and design, both acted on
- [x] Final kick-the-tires exploration and feedback completed (after slice 10) — learner tried the app and reported "done its good"; earlier hands-on feedback (no design, no motion) was resolved before this

## Final Review

<!-- Add agreed revision tasks as unchecked boxes here. -->

- [x] Final review complete — feedback resolved and learner confirms ready to ship (no further changes requested; known limits listed to the learner: JavaScript-only careers pages make PROCEED rare, small companies end Unknown, 40–70 s per run, 50 free requests a day, exposed key to rotate)

## Code Tour and App Map

<!-- Filled in after final review, during the learning wrap-up. -->

- [x] Learning activity complete — prior practice connected (focused alternative)
- [x] Optional edit and transfer reflection addressed — edit not applicable (familiar plan-first learner, practice came from a real bug); transfer question offered
- [x] `devpost/app-map.html` generated from finished code, checked, and shown, including a project-grounded practice to reuse

Activity and evidence: connected the learner's goal (how an agent decides a search proved or disproved a claim) to the live no-fee misread: the model mislabelled an observation, the separate code rules made the faulty input easy to pinpoint, fixed by `backend/app/evidence/no_fee.py` and `test_no_fee_statement_is_never_a_payment_request`.
Route and stops: reference route only (not toured): `extract.py` `check_quotes` → `status.py` `opportunity_status` / `decide` → `pipeline.py` `run_investigation` / `check_official_sources`.
Edit outcome: not applicable.
Reflection: offered (one optional question).
Activity mode: prior practice connected; map checked in the browser via its DOM (no scripts, no external resources, no overflow) — screenshot not possible because the pane was hidden.

## Revisions

- Search and a browser added, at the learner's request ("use both"), because the official-site check was the main reason real jobs ended at VERIFY FIRST:
  - Careers pages that need JavaScript are read in headless Chromium through Scrapling's `DynamicFetcher`. At most 2 such pages per investigation, about 8–12 s each, and every request inside the browser passes the private-address guard. Live: careers.infosys.com went from 13 characters to 3,702.
  - SerpAPI search (optional key) finds the official site when the proposed domain fails, and the listing on the official site when the careers pages don't show the role. The identity checks and a page read still decide; a search snippet alone never verifies. At most 2 searches per investigation, cached for 7 days, because the learner has about 167 searches left.
  - The fetch limit rose from 8 to 10 for the search fallback's pages.
  - The model client now retries once per investigation after a passing failure (timeout, 5xx, busy provider, garbled answer). The retry brings its own call, so later steps keep theirs. The daily-cap 429 is never retried and now says when it resets.
  - Verified: 168 tests pass, and no test can start a real browser or spend a real search. Live: the Infosys message still gives STOP in 54 s with 4 calls and 0 searches.
- Company names with department words ("Amazon HR") no longer require "HR" on the official site.
- Input audit, at the learner's request ("find every condition a user can put in that the app isn't ready for, then fix it"). Fixed:
  - A PDF or image link crashed the scraper (`UnicodeDecodeError`), including when an official careers link was a PDF. Now refused with a plain reason.
  - Outdated or closed posts (learner decision: VERIFY FIRST with its own advice, never STOP for age alone; stale after 30 days). Signs used: post age, passed deadline, graduated batch, and "No longer accepting applications".
  - OTP, PIN, card or password requests now mean STOP. Aadhaar, PAN or bank-detail requests hold back a Proceed. "We never ask for your OTP" is not a request.
  - Recruiter emails and links are compared with the official domain: personal webmail, forms and shorteners, and other domains hold back a Proceed; look-alike domains such as `nexora-careers.in` mean STOP.
  - Text that isn't a job offer gets a plain message, and pastes under 3 words are refused before any model call. An empty model answer on text with job words is retried once outside the budget, after a live run showed the free model sometimes returns nothing.
  - A post that lists several offers says which one was checked.
  - The careers page is found at `careers.<domain>` or `<domain>/careers` when the homepage has no link (google.com was Unknown before; now established).
  - Up to 3 screenshots are read in one vision call. Other image types are converted, and images over 4 MB are shrunk instead of refused.
  - Links without `https://`, and short share messages around a job-board link, are treated as links.
  - Dropping a PDF shows a message instead of the browser opening the file.
- Verified: 137 tests pass; frontend type-check is clean. Live checks:
  - Two chat screenshots with a fee and an OTP request ended STOP, with the OTP first.
  - The 3-year-old LinkedIn post ended VERIFY FIRST with the outdated advice.
  - A Hinglish recruiter message was extracted with every quote intact.
  - "hello there", a 34.5 MB image and a dropped PDF behaved as designed in the browser.
- The three limits left by the audit, fixed at the learner's request:
  - Text typed alongside screenshots is now read with them. Each quote says whether it came from the screenshot or the typed text.
  - Task scams (paid likes, ratings, "prepaid tasks") are a STOP before any fee is asked when the role is not verified, and a caution when it is. The model labels the claim, and a word check confirms it. Live: an "Amazon HR" like-and-rate message was labelled `task_scheme`.
  - A company whose official site can't be established can't be verified safely: using a domain taken from the message would let the scammer vouch for themselves. VERIFY FIRST now comes with steps to check it yourself (LinkedIn page, the MCA register, an offer letter from a company email).
  - 142 tests pass.
- The frontend dev server was serving a stale mixed build (`main-app.js` 404, page not interactive). Fixed by restarting it with a clean `.next`.

- LinkedIn links now read, at the learner's request: the old login-wall rule rejected public LinkedIn job pages whose full description sits under the sign-in boxes. Job links go through LinkedIn's public `jobs-guest` view, post links (`/posts/…`, `/feed/update/urn:li:…`) through the `embed` view, `lnkd.in` short links are followed to their target, and sign-in boxes are stripped before the readability check. When nothing readable is left, the message asks for a screenshot or the pasted text. Verified: 98 tests pass; live, two LinkedIn internship listings and two LinkedIn posts read in one fetch each; a removed job gives the screenshot message in the app; a full live run on a LinkedIn post finished VERIFY FIRST. Still not covered: how old the post is (a 3-year-old post was treated like a new one).

- Before publishing, at the learner's request: removed the personal story from `scope.md` ("Why This Matters to the Learner") and made "Who It's For" describe students generally rather than the learner's own experience.

- Live-model verification after the cap reset (all passed): slice 4 — Infosys-impersonation message: infosys.com established on all 6 signals, careers page read, internship Unverified, ₹1,500 UPI fee → STOP (4 calls, 5 fetches, 0 dropped quotes); slice 8 — that run's self-challenge wrote 3 counter-hypotheses and checked 3 real infosys.com pages, no change; slice 9 — that run saved as `app/samples/cached_case.json`; slice 5 — a real python.org job link read and investigated (small employer, no domain proposed → Unknown → VERIFY FIRST, the accepted small-company tradeoff); slice 6 — the chat screenshot transcribed exactly, 6/6 stages, STOP (4 calls); slice 3 — the fee case is STOP live (screenshot run) and the no-fee Microsoft posting is VERIFY FIRST live.
- Bug found by the live run and fixed: the model labelled "Microsoft never charges candidates any fee" as a fee, which made a legitimate posting STOP. Fixed in the extraction prompt and with a deterministic guard (`app/evidence/no_fee.py`): a no-fee statement is reclassified before the rules run and never counts as a payment request. Regression test added; re-run live gives VERIFY FIRST with no payment records.
- Vision model switched from `google/gemma-4-31b-it:free` to `dots-studio/dots-3-note-preview:free`: both Gemma free endpoints returned upstream 429s at the source; dots transcribed the screenshot exactly. `read_image` allows 8,000 tokens because dots spends tokens on reasoning first.

- Motion layer added after the learner found the site static: the laser beam now follows the pointer (its listener sits on its own container, which the page covered), plus a decoding hero word, a paste-box scan sweep, a breathing Investigate glow, and staggered result entrances with a decision stamp and hover lift. Reduced-motion users get none of it. Verified: production `next build` compiles cleanly; the page renders and settles in the browser.

- Look and Feel replaced after slice 10: the learner said the calm light design had "no design" and asked for threeui.com and "the best suitable design". New direction: dark X-ray film with ThreeUI Community's free `LaserCollection` beam behind the page (`components/XrayBackdrop.tsx`), cyan-white accent, evidence colors kept for meaning only. Copying ThreeUI Pro source was declined (paid, no redistribution); the learner agreed to free components. Verified in the browser at desktop and 375px for the paste, progress, and result views. PRD, spec, and README updated.

- Slice 10: applied the approved look with guidance from the minimalist-ui skill where it fits (Newsreader serif for the name and decision, warm monochrome tokens, muted pastel status badges: red contradiction, yellow unverified, green verified; divider accordions with +/−); skipped its gradients, ambient blobs and scroll animations because the spec allows motion only during an investigation. Fixed a slice-1 bug: font variables sat on `<body>` while the tokens on `:root` referenced them, so the body fell back to a default serif. Verified in the browser at desktop and 375px (no horizontal scroll; no gradients or shadows in the CSS).
- Spec updated to match the build: start-then-poll API, `GET /api/example`, and the added files (`jobs.py`, `progress.py`, `quotes.py`, `input/__init__.py`, `samples/__init__.py`, `scripts/save_example.py`, `transcribe.md`).

- Slice 9 committed before the example itself exists: `GET /api/example`, the loader that forces every record to Cached and refuses a file without a save date, `backend/scripts/save_example.py` (runs one real investigation and saves it), the "Try an example" link, and the cached banner are built and tested (5 tests; browser shows the plain "not been saved yet" message). Saving the real example from `tests/fixtures/realworld/india_internship_upi.txt` (Infosys name, UPI fee) is due after the model cap resets.

- Slice 8 committed before its live-model run (cap exhausted). Design detail: call 4 writes counter-hypotheses and may only choose pages from a numbered list of links found on the official site (invented IDs are ignored); code fetches them and applies fixed checks (the role title or an alternate title on an official page → Verified; an official "never charges candidates" statement plus a payment request → Contradiction), so no fifth model call is needed to read the new pages. If call 4 fails, the first decision stands and the result says the self-challenge could not run. Verified: 9 challenge tests (change VERIFY FIRST→PROCEED and VERIFY FIRST→STOP, no change says so, invented links ignored, lighter challenge for PROCEED, runs without official links, cites only real records, failure keeps first decision) and the browser view against the canned backend.

- Slice 7: the API became start-then-poll (`POST` returns 202 and an id; `GET` returns steps, then the result or a plain error). Step tracking lives in `app/investigation/progress.py` and the in-memory job store in `app/jobs.py` (not named in the spec's file tree). Verified with 4 progress tests and in the browser against a canned-model backend with a delay (midway: read done, extraction active; then the STOP result). The scan line is a plain line, not a gradient, to match the approved look.

- Slice 6 committed before its live-model run (cap exhausted). Verified: 10 screenshot tests (bad type, fake PNG, over-4 MB refused before any model call; transcription shown and used; excerpts checked against the transcription; NO_TEXT gives a plain error; budget 5 for images and 4 otherwise). `llm_client.py` gained `read_image()` for the vision model (`VISION_MODEL`, default `google/gemma-4-31b-it:free` at first). A generated chat-style screenshot of the fee conversation (`backend/tests/fixtures/fee_screenshot.png`, made with Pillow as a dev-only tool) is ready for the live run.

- Slice 5 committed before its live-model run (cap exhausted). Verified: 11 link tests (private addresses refused before any request, login wall and blocked pages give the paste-instead message, linked page produces the same stages, linked facts stay user-provided, one fetch from the shared budget) and live link reading of python.org/jobs and an Internshala listing (read) plus LinkedIn and Naukri (plain paste-instead message).

- Slice 4 code committed before its live-model verification, at the learner's direction, because the free-model daily cap was exhausted; the box stays unchecked until the live run after the reset. Already verified: 48 tests (fixtures for verified, unverified, blocked, JavaScript-only, look-alike, name-only, no-fee-policy contradiction, budget), and the live domain check plus careers discovery on infosys.com, tcs.com, wipro.com, microsoft.com and python.org (all established, all careers pages readable).
- Careers discovery prefers strong words (careers, jobs, join us, hiring) and only falls back to weaker ones; URLs are normalized and identical pages read once — the live check picked Microsoft's "Students and educators" page and fetched Infosys' careers page twice.
- Scrapling needs its `fetchers` extra (`scrapling[fetchers]`), and the scraper follows redirects itself so every hop passes the private-address guard.

- Slice 3 live check ran the real pipeline and rules with the model call replaced by a canned extraction (STOP for the fee conversation, VERIFY FIRST without the fee, confirmed in the browser), because the OpenRouter free-model daily cap (50 requests) was exhausted; a live-model re-run is due once the cap resets. The cap is a demo and judging risk to resolve before deployment.

- Link and screenshot input added as slices 5 and 6, after the official-site check (later slices renumbered 7–10); the model-call budget is 5 for screenshot investigations — the learner asked for every input type, especially links, during slice 2. Scope, PRD, and spec updated to match.

- Slice 2 learner check performed by the agent at the learner's request: 7 composite messages based on FTC and CyberPeace scam patterns (plus a legitimate posting and a prompt-injection attempt) in `backend/tests/fixtures/realworld/`, expected stages written before running; 7/7 matched on the live free model. Generous stage calls noted ("training kit link" counted as a training pitch).

- Reasoning moved from the Claude API to OpenRouter free models (`nvidia/nemotron-3-super-120b-a12b:free` by default, configurable), with no backup provider; `claude_client.py` became `llm_client.py` — the learner chose free models during slice 2. Accepted tradeoffs: about 12 investigations a day on the free tier, possible prompt logging by free providers, and less reliable structured output.
- Quote check lives in `app/evidence/quotes.py`, shared by extraction and (later) page observations — the spec named the test but not the module.

- Look and Feel now allows restrained CSS scan motion during an active investigation (first-screen start and progress view only), with the result and evidence static; Three.js and threeui.com rejected — learner asked for a cooler, animated feel mid-build and chose the mix option to keep the evidence calm and avoid a new dependency.
- Python 3.13 used instead of the spec's 3.12 — it is the version installed on the learner's machine; no code depends on the difference.

