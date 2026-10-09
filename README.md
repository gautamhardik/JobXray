# JobXray

**X-ray the job before you apply.** JobXray investigates a suspicious job or internship offer before you pay, apply, or share anything. Paste the recruiter messages, a link to the posting, or a screenshot. JobXray reads the recruitment funnel, checks the claimed opportunity against the company's official website, challenges its own first verdict, and tells you to **Proceed**, **Verify First**, or **Stop**, with the evidence behind it.

Built for Devpost's *Build With AI: Basics* hackathon with the Devpost Learn skill pack. The planning documents are in [`devpost/`](devpost/): [`scope.md`](devpost/scope.md), [`prd.md`](devpost/prd.md), [`spec.md`](devpost/spec.md), and the build [`checklist.md`](devpost/checklist.md).

## How it decides

- **The model reads; code decides.** An AI model extracts claims and funnel stages, proposes the company's real domain, and reports what official pages say, quoting them. Every quote is checked against its source and dropped if it isn't really there. Fixed rules in `backend/app/evidence/status.py` turn the evidence into a status and a decision.
- **Evidence labels:** Fact (from what you provided), Verified, Unverified (an official page was read and did not confirm it), Unknown (could not be established or reached), Contradiction.
- **Never certainty from missing evidence.** An unreachable site or a missing listing is Unknown or Unverified, never "fake".
- **Official means official.** A domain from the message never counts. The proposed domain must pass several first-party identity checks; a name match alone is not enough.
- **Self-challenge every time.** After the first verdict, JobXray looks for evidence that could prove it wrong, on the official site only, and shows any change on the main answer.

## Run it locally

Requirements: Python 3.12+, Node.js 20+, and an [OpenRouter](https://openrouter.ai) API key (free models work).

```bash
cd backend
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt   # on macOS/Linux: .venv/bin/python
cp .env.example .env                                       # then add your OPENROUTER_API_KEY
.venv/Scripts/python -m uvicorn app.main:app --port 8000
```

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000. The frontend reads the backend address from `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`).

**Environment (`backend/.env`, never committed):** `OPENROUTER_API_KEY`, `OPENROUTER_MODEL` (default `nvidia/nemotron-3-super-120b-a12b:free`), `VISION_MODEL` for screenshots (default `dots-studio/dots-3-note-preview:free`).

**Limits per investigation:** 10,000 characters of text, 8 page fetches, 4 model calls (5 for screenshots), one self-challenge round. Free OpenRouter models allow 50 requests a day on a new account (about 12 investigations).

**Example without the model:** after saving one real run with `python -m scripts.save_example tests/fixtures/realworld/india_internship_upi.txt` (from `backend/`), "Try an example" loads it offline, labelled Cached.

## Tests

```bash
cd backend
.venv/Scripts/python -m pytest -q
```

The tests replace the model and the web with scripted doubles and saved pages, so they run offline. `backend/tests/fixtures/realworld/` holds composite scam messages based on patterns described by the [FTC](https://consumer.ftc.gov/node/331470) and [CyberPeace](https://cyberpeace.org/resources/blogs/internship-scams-exposing-financial-frauds-targeting-students).

## Stack

Next.js (frontend), FastAPI (backend), [Scrapling](https://github.com/D4Vinci/Scrapling) for fetching pages, OpenRouter free models for reasoning. The X-ray beam behind the page is `LaserCollection` from [ThreeUI Community](https://threeui.com) (`@designcodeio/threeui`, MIT). No database: investigations live in memory and disappear on restart.
