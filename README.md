# Darwix AI Voice Agent — AI Engineer Assessment

**Candidate:** Nikhil Kumar  
**Stack:** Python 3.11 · FastAPI · Groq (LLM + Whisper STT) · Google Gemini (embeddings + fallback LLM) · Edge-TTS · Qdrant · SQLite  
**Zero-cost-first:** No paid APIs are required for core functionality. All providers used are free-tier or fully free.

---

## Table of Contents

1. [Business Problem](#1-business-problem)
2. [Architecture](#2-architecture)
3. [Repository Structure](#3-repository-structure)
4. [Setup](#4-setup)
5. [Running the System](#5-running-the-system)
6. [Technology Choices](#6-technology-choices)
7. [Q1 — Voice Agent (Health Insurance Lead Qualification)](#7-q1--voice-agent)
8. [Q2 — Production-Ready Knowledge Base](#8-q2--production-ready-knowledge-base)
9. [Q3 — Multilingual Voice Bots](#9-q3--multilingual-voice-bots)
10. [Q4 — Real-Time Call Intelligence](#10-q4--real-time-call-intelligence)
11. [Environment Variables](#11-environment-variables)
12. [Submission Checklist](#12-submission-checklist)
13. [Known Limitations](#13-known-limitations)
14. [Production Improvement Plan](#14-production-improvement-plan)

---

## 1. Business Problem

Insurance companies sit on large volumes of unstructured business data — policy PDFs, website FAQs, objection-handling guides, pricing tables, and forms. Agents who answer qualification calls must search across all of this manually, often improvising answers that may be inaccurate or non-compliant.

This system solves that end-to-end:

1. **Unstructured data** (PDFs, web pages, tables, FAQs) is ingested, cleaned, de-duplicated, chunked, embedded, and stored in a searchable vector database.
2. A **grounded voice agent** retrieves relevant context from that database before answering every question — it never invents policy information it does not have.
3. The system **qualifies health insurance leads** through a natural conversation, handling objections, extracting lead fields, recommending plans, and creating CRM records.
4. The same architecture extends to **Philippines (Taglish)** and **Indonesia (Bahasa Indonesia)** markets with culturally appropriate localization — not simple translation.
5. A **real-time call intelligence layer** streams live audio, detects signals (frustration, compliance gaps, cross-sell opportunities), and pushes actionable nudges to an agent dashboard within milliseconds.

The result is a coherent end-to-end AI system: from raw business data to a grounded, measurable, multilingual voice agent with live intelligence.

---

## 2. Architecture

### Core Voice Pipeline (Q1 + Q2)

```
┌─────────────────────────────────────────────────────────────────┐
│                         BROWSER                                  │
│           Microphone ──── Speaker                               │
└────────────────┬───────────────────────────────────────────────┘
                 │  WebSocket (binary audio frames + JSON control)
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│              FastAPI Voice Server  (port 8000)                  │
│              q1_voice_agent/voice_server.py                     │
│                                                                 │
│   WebSocket /voice/{session_id}                                 │
│   GET        /voice-call          ← browser UI                  │
│   GET        /health                                            │
└────────┬──────────────────────────────────┬────────────────────┘
         │                                  │
         ▼                                  ▼
┌─────────────────┐              ┌──────────────────────────────┐
│ Groq Whisper    │              │        VoiceAgent             │
│ whisper-large   │              │  q1_voice_agent/agent.py      │
│ -v3-turbo       │              │                               │
│ (STT, ~400ms)   │              │  ┌─────────────────────────┐  │
└────────┬────────┘              │  │  QualificationState      │  │
         │  transcript           │  │  LeadProfile             │  │
         └──────────────────────►│  │  Regex lead extractor    │  │
                                 │  └─────────────────────────┘  │
                                 │              │                  │
                                 │              ▼                  │
                                 │  ┌─────────────────────────┐  │
                                 │  │    Q2 Retriever          │  │
                                 │  │  (Qdrant + Gemini embed) │  │
                                 │  └───────────┬─────────────┘  │
                                 │              │  grounded ctx   │
                                 │              ▼                  │
                                 │  ┌─────────────────────────┐  │
                                 │  │      LLM Router          │  │
                                 │  │  Groq compound-mini      │  │
                                 │  │      ↓ (on fail)         │  │
                                 │  │  Gemini 2.5 Flash        │  │
                                 │  └───────────┬─────────────┘  │
                                 │              │  response text  │
                                 └──────────────┼─────────────────┘
                                                │
                         ┌──────────────────────┼──────────────────┐
                         │                      │                  │
                         ▼                      ▼                  ▼
              ┌─────────────────┐   ┌─────────────────┐  ┌────────────────┐
              │   Edge-TTS      │   │  SQLite CRM      │  │  Lead Panel    │
              │ en-US-AriaNeural│   │  upsert_lead()   │  │  (WebSocket    │
              │  (MP3 audio)    │   │  darwix.db       │  │   JSON event)  │
              └────────┬────────┘   └─────────────────┘  └────────────────┘
                       │ binary audio
                       └──────────────────────────────► Browser Speaker
```

### Q4 Real-Time Call Intelligence

```
┌────────────────────────────────────────────────────────────────┐
│             Live Audio / Simulation Input                       │
└──────────────────────┬─────────────────────────────────────────┘
                       │  audio chunks (3s)
                       ▼
              Groq Whisper STT
                       │  transcript chunks
                       ▼
┌──────────────────────────────────────────────────────────────┐
│                   Signal Detector                             │
│  q4_live_insights/signal_detector.py                         │
│                                                              │
│  Pass 1 — Rule-based  (every chunk, <5ms)                    │
│    Keyword/regex matching: frustration, compliance,          │
│    buying signals, cross-sell triggers, escalation           │
│                                                              │
│  Pass 2 — LLM-based   (every 3rd final chunk, ~400-800ms)    │
│    Groq llama-3.1-8b-instant on rolling transcript window    │
│    Returns JSON: signal_type + confidence + trigger_quote    │
└──────────────────────┬───────────────────────────────────────┘
                       │  List[DetectedSignal]
                       ▼
┌──────────────────────────────────────────────────────────────┐
│                    Nudge Engine                               │
│  q4_live_insights/nudge_engine.py                            │
│                                                              │
│  Quality controls applied (in order):                        │
│  1. Confidence threshold (≥0.65)                             │
│  2. Cooldown per signal type (15-90s)                        │
│  3. Max active nudges cap (5)                                │
│  4. Repetition penalty (>2 occurrences → -0.10 confidence)  │
│  5. Short utterance filter (<4 words → skip LLM)            │
│  6. Topic grouping (same type within 10s → one nudge)        │
│  7. Expiry TTL (30-180s per signal type)                     │
└──────────────────────┬───────────────────────────────────────┘
                       │  List[Nudge]
                       ▼
              WebSocket / HTTP API
                       │
                       ▼
              Agent Dashboard (port 8003)
```

### Provider Abstraction Layer

```
shared/providers.py
│
├── LLMRouter
│     ├── GroqProvider          (groq/compound-mini, primary)
│     └── GeminiProvider        (gemini-2.5-flash, fallback on 429/timeout)
│
├── GroqWhisperProvider         (whisper-large-v3-turbo, multilingual)
│
├── EdgeTTSProvider             (no API key, en/fil-PH/id-ID voices)
│
└── EmbeddingProvider
      ├── GeminiEmbeddingProvider  (gemini-embedding-001, 3072-dim, primary)
      └── LocalHashEmbeddingProvider  (offline fallback, zero cost, poor quality)
```

---

## 3. Repository Structure

```
darwix-ai-assessment/
│
├── README.md                          ← this file
├── .env                               ← your local secrets (gitignored)
├── .env.example                       ← template (committed)
├── .gitignore
├── Require.md                         ← assessment brief
├── requirements.txt                   ← all Python dependencies
├── darwix.db                          ← SQLite CRM database
│
├── shared/                            ← shared infrastructure
│   ├── __init__.py
│   ├── providers.py                   ← LLM / STT / TTS / Embed abstractions ★
│   ├── database.py                    ← SQLite lead storage
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py                ← pydantic-settings env loader
│   └── utils/
│       └── __init__.py                ← structured logger
│
├── q1_voice_agent/                    ← Q1: health insurance voice agent
│   ├── __init__.py
│   ├── voice_server.py                ← FastAPI app + WebSocket voice pipeline ★
│   ├── agent.py                       ← VoiceAgent core (LLM + KB + state)
│   ├── prompts.py                     ← system prompt, objection handling, flows
│   ├── qualification.py               ← QualificationState + LeadProfile + rules
│   ├── stt.py                         ← STT helpers
│   └── telephony.py                   ← text-mode backup API
│
├── q2_knowledge_base/                 ← Q2: KB pipeline
│   ├── __init__.py
│   ├── schema.py                      ← KBRecord / RetrievalResult pydantic models
│   ├── cleaner.py                     ← text cleaning, PII detection, dedup
│   ├── chunker.py                     ← paragraph-aware semantic chunker
│   ├── embedder.py                    ← embedding + Qdrant upsert
│   ├── retriever.py                   ← vector search + reranking + grounded answer
│   ├── ingest.py                      ← full pipeline runner (run this first)
│   ├── api.py                         ← FastAPI KB search API (port 8001)
│   ├── retrieval_test_results.md      ← 5 query evaluation results
│   ├── data/
│   │   ├── raw/
│   │   │   └── health_insurance_source.json   ← 10 source documents (mock)
│   │   └── cleaned/
│   │       └── kb_records.json                ← cleaned + chunked KB records
│   └── embeddings/                    ← Qdrant local on-disk storage
│       └── collection/darwix_kb/
│           └── storage.sqlite
│
├── q3_multilingual/                   ← Q3: Philippines + Indonesia bots
│   ├── __init__.py
│   ├── api.py                         ← FastAPI multilingual API (port 8002)
│   ├── market_comparison.md           ← PH vs ID localization comparison
│   ├── philippines/
│   │   ├── __init__.py
│   │   ├── agent_ph.py                ← Philippines VoiceAgent (Taglish)
│   │   └── prompts_ph.py              ← Taglish scripts + localization examples
│   └── indonesia/
│       ├── __init__.py
│       ├── agent_id.py                ← Indonesia VoiceAgent (Bahasa)
│       └── prompts_id.py              ← Bahasa scripts + localization examples
│
├── q4_live_insights/                  ← Q4: real-time call intelligence
│   ├── __init__.py
│   ├── models.py                      ← SignalType, Nudge, CallSession pydantic models
│   ├── signal_detector.py             ← rule-based + LLM signal detection
│   ├── nudge_engine.py                ← quality controls + nudge generation
│   ├── pipeline.py                    ← full streaming pipeline orchestrator
│   ├── api.py                         ← FastAPI live insights API (port 8003)
│   ├── run_demo.py                    ← CLI simulation demo
│   ├── simulation_scenarios.py        ← 4 test scenarios
│   ├── latency_report.md              ← measured P50/P95 results
│   └── dashboard/                     ← agent nudge dashboard (HTML/WS)
│
└── docs/
    ├── architecture/                  ← architecture diagrams
    └── transcripts/                   ← recorded call transcripts
        ├── q1_call_01_cooperative.md
        ├── q1_call_02_objections.md
        ├── q1_call_03_incomplete_conflicting.md
        ├── q3_ph_call_01_cooperative_taglish.md
        ├── q3_ph_call_02_objection_escalation.md
        ├── q3_id_call_01_installment_reminder_javanese.md
        ├── q3_id_call_02_qualification_mixed_english.md
        └── q4_simulation_results.md
```

---

## 4. Setup

### Prerequisites

- Python 3.11+
- A [Groq API key](https://console.groq.com) (free — used for LLM and Whisper STT)
- A [Google AI Studio key](https://aistudio.google.com) (free — used for Gemini embeddings and LLM fallback)

### Install

```bash
# Clone the repository
git clone https://github.com/your-username/darwix-ai-assessment.git
cd darwix-ai-assessment

# Create and activate a virtual environment
python3.11 -m venv venv
source venv/bin/activate          # macOS / Linux
# venv\Scripts\activate           # Windows

# Install dependencies
pip install -r requirements.txt
```

### Configure environment

```bash
cp .env.example .env
```

Open `.env` and set at minimum:

```env
GROQ_API_KEY=gsk_...          # required — LLM + STT
GOOGLE_API_KEY=AIza...        # required — embeddings + LLM fallback
```

Everything else has sensible defaults and is optional for the prototype.

### Build the Knowledge Base

This step ingests raw source data, cleans it, chunks it, embeds it with Gemini, and stores it in Qdrant on-disk. Run it once before starting any service.

```bash
python3 -m q2_knowledge_base.ingest
```

Expected output:
```
INFO  ingestion_started    records=10
INFO  cleaning_complete    records=10  pii_flagged=0  duplicates_removed=0
INFO  chunking_complete    chunks=34
INFO  embedding_complete   chunks=34   model=gemini-embedding-001
INFO  qdrant_upsert        collection=darwix_kb  vectors=34
INFO  ingestion_complete   elapsed_s=12.4
```

---

## 5. Running the System

Each component runs as an independent FastAPI service. Start only what you need.

### Q1 — Voice Agent (primary interface)

```bash
./venv/bin/uvicorn q1_voice_agent.voice_server:app --host 0.0.0.0 --port 8000
```

Open **http://localhost:8000/voice-call** in your browser.  
Click the microphone button, speak, and release to send. Aria will respond with synthesised voice.

### Q1 — Text backup (telephony API)

```bash
./venv/bin/uvicorn q1_voice_agent.telephony:app --host 0.0.0.0 --port 8000
```

Open **http://localhost:8000** for a simple text-based conversation interface. Useful for testing without a microphone.

### Q2 — Knowledge Base API

```bash
./venv/bin/uvicorn q2_knowledge_base.api:app --host 0.0.0.0 --port 8001
```

Search endpoint: `POST http://localhost:8001/search`  
Health check: `GET http://localhost:8001/health`

Example query:
```bash
curl -X POST http://localhost:8001/search \
  -H "Content-Type: application/json" \
  -d '{"query": "what is the waiting period for pre-existing conditions", "top_k": 3}'
```

### Q3 — Multilingual API

```bash
./venv/bin/uvicorn q3_multilingual.api:app --host 0.0.0.0 --port 8002
```

Endpoints:
- `POST /ph/respond` — Philippines bot (Taglish)
- `POST /id/respond` — Indonesia bot (Bahasa Indonesia)

### Q4 — CLI Simulation Demo

Runs 4 pre-built scenarios locally with no microphone required. Prints detected signals, nudges, and latency measurements.

```bash
python3 -m q4_live_insights.run_demo
```

### Q4 — Live Insights Dashboard

```bash
./venv/bin/uvicorn q4_live_insights.api:app --host 0.0.0.0 --port 8003
```

Open **http://localhost:8003** to see the real-time nudge dashboard.

---

## 6. Technology Choices

| Component | Provider / Tool | Reason |
|---|---|---|
| LLM (primary) | Groq `groq/compound-mini` | Free tier, fast inference, handles long context well without function-calling dependency |
| LLM (fallback) | Gemini `gemini-2.5-flash` | Free tier, activates automatically on Groq 429 / timeout |
| STT | Groq Whisper `whisper-large-v3-turbo` | Free tier, ~400ms latency, supports 90+ languages including Tagalog and Bahasa Indonesia |
| TTS | Edge-TTS | Fully free, no API key, native `fil-PH-BlessicaNeural` and `id-ID-GadisNeural` voices available |
| Embeddings | Google `gemini-embedding-001` | Free tier, 3072 dimensions, multilingual, already configured with Gemini key |
| Embeddings (offline fallback) | `LocalHashEmbeddingProvider` | Deterministic hash-based vectors — zero cost, zero network, poor retrieval quality (dev only) |
| Vector DB | Qdrant (local on-disk) | No Docker, no cloud, no cost. `qdrant-client` embeds a full local instance at `q2_knowledge_base/embeddings/` |
| Database | SQLite | Zero setup, sufficient for lead storage and prototype CRM. File at `darwix.db` |
| Web framework | FastAPI | Async-native, built-in WebSocket support, fast enough for voice latencies |
| Signal detection (fast path) | Rule-based regex | <5ms per chunk. Covers well-defined signals: frustration keywords, buying signals, compliance gaps |
| Signal detection (nuanced) | Groq `llama-3.1-8b-instant` | Fastest free Groq model. Batched every 3 chunks to minimise cost and latency |

**Explicitly avoided:** OpenAI (cost), ElevenLabs (limited free tier), Pinecone (cloud cost), Twilio (PSTN cost), Redis (not needed at prototype scale), Docker (friction for setup).

---

## 7. Q1 — Voice Agent

### Use Case

**Health insurance lead qualification** — Aria calls prospective customers, qualifies them for a suitable plan, handles objections using KB-grounded responses, and creates a CRM record on qualification.

### Conversation Flow

```
GREETING
    ↓
QUALIFYING (name → age → smoker → pre-existing → dependents → budget)
    ↓
OBJECTION HANDLING (KB-grounded, if needed)
    ↓
PLAN RECOMMENDATION
    ↓
CLOSING (contact capture → callback schedule → CRM upsert)
    ↓
DONE / ESCALATE
```

The agent maintains a `QualificationState` across the full conversation. Lead fields are extracted from each utterance using a fast regex parser (no LLM needed for data extraction). The LLM is used only for conversational response generation.

### Qualification Rules

| Rule | Detail |
|---|---|
| Age eligibility | 18–65 years old at time of application |
| Smoker loading | +15% on base monthly premium |
| Dependents | +60% of base premium per dependent |
| Pre-existing (Standard/Premium) | Covered after 12-month waiting period |
| Pre-existing (Basic) | Excluded entirely |
| BMI > 40 | Flagged for specialist underwriting review |
| Out-of-scope question | Safe fallback — never hallucinate |
| Human escalation triggers | Explicit request, repeated misunderstanding, compliance concern, low confidence |

### Plan Reference

| Plan | Monthly Premium | Hospitalisation Limit | Outpatient | Dental |
|---|---|---|---|---|
| Basic | PHP 1,200 | PHP 100,000 | No | No |
| Standard | PHP 2,500 | PHP 300,000 | 6 visits/year | No |
| Premium | PHP 4,800 | PHP 1,000,000 | Unlimited | Yes |

### Outcome States

| Outcome | Condition |
|---|---|
| `QUALIFIED` | Age eligible, contact number captured, plan identified |
| `NOT_QUALIFIED` | Age outside 18–65 |
| `FOLLOW_UP` | Partial information — callback scheduled |
| `ESCALATE` | Customer requested human, or agent flagged complexity |

### Recorded Test Calls

| # | Scenario | Outcome | Transcript |
|---|---|---|---|
| 1 | Cooperative customer — complete qualification | QUALIFIED | `docs/transcripts/q1_call_01_cooperative.md` |
| 2 | Objection handling — "I already have company insurance" | FOLLOW_UP | `docs/transcripts/q1_call_02_objections.md` |
| 3 | Incomplete/conflicting details — age conflict, partial data | FOLLOW_UP | `docs/transcripts/q1_call_03_incomplete_conflicting.md` |

---

## 8. Q2 — Production-Ready Knowledge Base

### Source Data

10 synthetic documents modelled on real health insurance content (clearly labelled as demo data — see `Require.md` §41):

| Source ID | Type | Content |
|---|---|---|
| `web_001` | website | Product overview |
| `web_002` | website | Eligibility requirements |
| `web_003` | website | FAQ — claims and general |
| `web_004` | website | Objection handling guide — Part 1 |
| `web_005` | website | Objection handling guide — Part 2 |
| `web_006` | website | Branch partner benefits |
| `web_007` | website | Contact and support |
| `pdf_001` | PDF | Full policy document (sections 1–5) |
| `csv_001` | table | Plan comparison table |
| `form_001` | form | Application form field definitions |

### Pipeline Steps

```
RAW JSON (health_insurance_source.json)
    ↓  cleaner.py
CLEANING
    Remove navigation text, headers/footers, HTML artifacts
    Flag and protect PII (email, phone, NIC patterns)
    Deduplicate exact and near-duplicate content
    Normalise headings, dates, terminology, currencies (PHP)
    ↓  chunker.py
CHUNKING (paragraph-aware semantic chunking)
    Respect paragraph/section boundaries
    Target chunk size: 400 tokens, overlap: 80 tokens
    Preserve: source_id, source_type, source_url, version, category, language
    ↓  embedder.py
EMBEDDING
    Google gemini-embedding-001 (3072-dim, multilingual)
    Batch API calls with retry on rate limit
    ↓  Qdrant (local on-disk, qdrant-client)
VECTOR STORE
    Collection: darwix_kb
    Path: q2_knowledge_base/embeddings/
    No Docker, no network service required
    ↓  retriever.py
RETRIEVAL
    Embed query → cosine similarity search (top_k=5)
    Metadata filter (category, language, score threshold)
    Keyword-boost reranking (+0.01 per overlapping token, cap +0.05)
    Min score threshold: 0.45
    Return grounded context + citations
```

### KB Record Schema

```json
{
  "record_id":      "kb_web_002_000",
  "title":          "Eligibility Requirements",
  "content":        "Applicants must be between 18 and 65 years of age...",
  "category":       "eligibility_rules",
  "source_id":      "web_002",
  "source_type":    "website",
  "source_url":     "https://example-insurer.com/eligibility",
  "version":        "1.0",
  "language":       "en-PH",
  "pii_present":    false,
  "tags":           ["age", "eligibility", "smoker", "pre-existing"],
  "created_at":     "2024-01-01T00:00:00",
  "chunk_index":    0,
  "chunk_total":    1
}
```

### Chunking Strategy

Paragraph-aware chunking is used over fixed-size splitting. Policy clauses and FAQ Q&A pairs are natural semantic units. Cutting mid-sentence reduces retrieval precision because the vector for a partial thought does not represent the full meaning.

- **Target size:** 400 tokens (~300 words) — fits a complete FAQ answer or policy section
- **Overlap:** 80 tokens (20%) — sentences near boundaries appear in at least two chunks
- **Boundaries preserved:** section headers, paragraph breaks, Q&A pairs

### Retrieval Evaluation Results

| # | Question Type | Top Record | Score | Verdict |
|---|---|---|---|---|
| 1 | Product | `kb_csv_001_000` (plan comparison table) | 0.87 | ✅ Correct |
| 2 | Policy / eligibility | `kb_web_002_000` (eligibility rules) | 0.91 | ✅ Correct |
| 3 | FAQ | `kb_pdf_001_002` + `kb_web_003_000` | 0.83 / 0.79 | ✅ Correct (multi-chunk) |
| 4 | Objection | `kb_web_005_001` (objection guide) | 0.84 | ✅ Correct |
| 5 | Out-of-scope | None — top candidate 0.21, below threshold | 0.21 | ✅ Safe fallback |

All 5 queries returned correct or safe results. No hallucinated answers observed. Full evaluation in `q2_knowledge_base/retrieval_test_results.md`.

---

## 9. Q3 — Multilingual Voice Bots

### Philippines Bot — Maya (Life Insurance / Bancassurance)

**Agent name:** Maya  
**TTS voice:** `fil-PH-BlessicaNeural` (Edge-TTS native Filipino voice)  
**Languages:** English, Filipino/Tagalog, natural Taglish code-switching  
**Sector:** Life insurance lead qualification + premium reminders

**Localization features:**

| Feature | Implementation |
|---|---|
| Taglish code-switching | Natural mixing of English and Tagalog mid-sentence — English for financial terms (premium, policy, beneficiary, rider), Tagalog for rapport and emotional framing |
| Politeness markers | `po` and `ho` used throughout. `Ma'am` / `Sir` for address |
| Family-first framing | Insurance positioned as protection for loved ones, not personal planning — primary cultural motivator |
| Bahala-na handling | Direct acknowledgment of Filipino fatalism by name, reframed as gift to family |
| Pakikisama (social harmony) | Offer language, never pressure. `Huwag mag-alala` (don't worry) tone |
| Bancassurance cross-sell | Separate script for bank partner cross-sell targeting existing bank customers |

**Recorded test calls:**
- `q3_ph_call_01_cooperative_taglish.md` — cooperative customer, natural Taglish throughout
- `q3_ph_call_02_objection_escalation.md` — objection + human escalation

### Indonesia Bot — Sari (Multifinance / Consumer Finance)

**Agent name:** Sari  
**TTS voice:** `id-ID-GadisNeural` (Edge-TTS native Indonesian voice)  
**Languages:** Formal Bahasa Indonesia, colloquial Bahasa, finance English loanwords, Javanese/Sundanese accent awareness  
**Sector:** Consumer finance — installment reminders + loan qualification

**Localization features:**

| Feature | Implementation |
|---|---|
| Finance terminology | Natural use of: `cicilan`, `tenor`, `denda`, `DP`, `jatuh tempo`, `angsuran`, `pembiayaan`, `lunas` |
| Menjaga muka (face-saving) | Collections language that never shames. Urgency framed as advice, not threat. Solutions offered immediately |
| Regional accent handling | Javanese `njeh`/`inggih` and Sundanese `muhun` detected and acknowledged — agent mirrors warmth, returns to standard Bahasa for content |
| Nanti dulu (soft refusal) | Recognised as soft avoidance, not hard no. Responded with low-friction follow-up (WhatsApp) |
| Colloquial Jakarta | `gue`/`lu` avoided in formal finance context — use `saya`/`Bapak`/`Ibu` throughout |
| WhatsApp-first follow-up | Indonesia's primary business channel — always offered as callback alternative |

**Recorded test calls:**
- `q3_id_call_01_installment_reminder_javanese.md` — installment reminder with Javanese accent customer
- `q3_id_call_02_qualification_mixed_english.md` — loan qualification with mixed English finance terms

### Localization vs Translation — Comparison Table

| Scenario | Literal Translation | Localized Output | Why Different |
|---|---|---|---|
| PH — Premium objection | "The insurance premium is too expensive." | "Alam ko pong may budget consideration kayo. Pero ang Basic Plan namin ay PHP 1,200 lang bawat buwan — mas mura pa 'yan sa isang family dinner sa labas." | Uses family dinner as a relatable cost anchor (PH context). Ends with reflection question, not a push. |
| PH — Bahala-na mindset | "You should think about what happens to your family." | "Naiintindihan ko po 'yung feeling na 'bahala na, basta mabuhay tayo.' Pero ang insurance po ay hindi para sa atin — para po ito sa mga taong mahal natin." | Names the cultural concept. Reframes from personal planning to gift-to-family. |
| ID — Late payment reminder | "Your payment is late. You will be charged a penalty." | "Mau mengingatkan bahwa angsuran Ibu bulan ini sudah jatuh tempo ya. Supaya tidak ada denda tambahan, apakah Ibu bisa melakukan pembayaran hari ini?" | Avoids blame. Frames urgency as advice. Offers immediate solution. Face-saving exit available. |
| ID — Nanti dulu objection | "Please decide soon." | "Tentu Bapak/Ibu, tidak ada masalah. Boleh saya hubungi kembali besok? Atau kalau ada pertanyaan, bisa langsung WhatsApp kami kapan saja." | Respects the soft refusal. Offers WhatsApp (Indonesia's primary channel). No pressure. |

### Known Gaps

- `fil-PH-BlessicaNeural` (Edge-TTS) is a high-quality Filipino voice but does not reproduce authentic Taglish rhythm for all utterance patterns. A professional Filipino TTS (e.g. Google Cloud `fil-PH-Standard-B` or a native ElevenLabs voice) would produce more natural results.
- Regional Indonesian accents (Javanese, Sundanese, Batak) are detected through keyword heuristics. There is no dedicated regional TTS voice available on Edge-TTS — all Indonesian output uses standard Jakarta `id-ID-GadisNeural`.
- Both bots have not been reviewed by native speakers. Fluency and cultural accuracy should be validated before production deployment.

---

## 10. Q4 — Real-Time Call Intelligence

**Critical requirement:** This is live analysis during the call, not post-call processing.

### Pipeline

```
Audio (live mic or simulation file)
    ↓  3-second chunks
Groq Whisper STT
    ↓  transcript chunk (is_final flag)
Signal Detector
    ├── Pass 1: Rule-based  (every chunk,  <5ms)   → keyword/regex matching
    └── Pass 2: LLM-based   (every 3rd final chunk, ~400-800ms) → nuanced signals
    ↓  List[DetectedSignal]
Nudge Engine  (quality controls applied)
    ↓  List[Nudge]
WebSocket push → Agent Dashboard
```

### Signal Catalogue

| Signal Type | Detection Method | Priority | Cooldown |
|---|---|---|---|
| `compliance_gap` | Rule (keyword) + LLM | High | 20s |
| `rising_frustration` | Rule (keyword) + LLM | High | 25s |
| `escalation_risk` | Rule (keyword) | High | 15s |
| `missed_cross_sell` | Rule (trigger map) + LLM | Medium | 45s |
| `payment_difficulty` | Rule (keyword) + LLM | Medium | 60s |
| `buying_signal` | Rule (keyword) | Medium | 30s |
| `objection` | LLM | Medium | 30s |
| `callback_request` | Rule (keyword) | Low | 60s |
| `topic_shift` | LLM | Low | 20s |

### Nudge Quality Controls

1. **Confidence threshold (≥0.65)** — signals below this generate no nudge, regardless of type
2. **Per-type cooldown (15–90s)** — same signal type will not repeat within its cooldown window
3. **Max active nudges (5)** — dashboard never shows more than 5 nudges simultaneously
4. **Repetition penalty** — confidence reduced by 0.10 for each occurrence beyond the second, preventing stale recurring signals from nudging
5. **Short utterance filter (<4 words)** — LLM detector skipped entirely for very short turns (noise, affirmations)
6. **Topic grouping** — signals of the same type within a 10-second window collapse into a single nudge
7. **Expiry TTL (30–180s)** — nudges auto-dismiss after their type-specific TTL to prevent stale alerts

### Measured Latency

Latency measured from **audio chunk received → nudge displayed on dashboard** across 4 simulation scenarios (38 total nudge events).

| Metric | Rule-Based | LLM-Based | Combined |
|---|---|---|---|
| P50 | 278ms | 748ms | 490ms |
| P95 | 390ms | 1,240ms | 960ms |
| Min | 215ms | 510ms | 215ms |
| Max | 520ms | 1,650ms | 1,650ms |

| Component | Avg Latency | Notes |
|---|---|---|
| ASR (Groq Whisper) | ~400ms | Per utterance, streaming |
| Signal detection (rule) | <5ms | Regex match |
| Signal detection (LLM) | ~520ms | Groq llama-3.1-8b-instant, batched every 3 chunks |
| Nudge generation (static) | <2ms | Dict lookup |
| Nudge generation (LLM) | ~480ms | For nuanced signals |
| WebSocket delivery | ~5ms | Local; add ~20ms for production network |

Full results including per-scenario breakdown and false-positive analysis in `q4_live_insights/latency_report.md`.

### False-Positive Summary

From 38 signals across 4 scenarios: ~2 estimated false positives (~5% FP rate on clean audio). 4 ambiguous signals correctly suppressed by confidence threshold. 2 valid-but-duplicate signals suppressed by cooldown.

### Running the Demo

```bash
python3 -m q4_live_insights.run_demo
```

The demo runs 4 built-in scenarios simulating: a missed cross-sell opportunity, a compliance gap, rising customer frustration, and a noisy/ambiguous call. Each scenario prints the detected signals, nudges fired, suppressed signals and their reasons, and component-level latency.

---

## 11. Environment Variables

Copy `.env.example` to `.env`. Only `GROQ_API_KEY` and `GOOGLE_API_KEY` are required to run the full prototype.

```env
# ── Required ──────────────────────────────────────────────────
GROQ_API_KEY=gsk_...                    # Groq — LLM + Whisper STT (free)
GOOGLE_API_KEY=AIza...                  # Google AI Studio — Gemini embeddings + fallback LLM (free)

# ── Optional enhancements ──────────────────────────────────────
ELEVENLABS_API_KEY=                     # Optional — higher-quality TTS fallback

# ── TTS voice selection ────────────────────────────────────────
TTS_VOICE_EN=en-US-AriaNeural           # Q1 English voice (Edge-TTS)
TTS_VOICE_FILIPINO=fil-PH-BlessicaNeural # Q3 Philippines voice
TTS_VOICE_INDONESIAN=id-ID-GadisNeural  # Q3 Indonesia voice

# ── Knowledge Base ─────────────────────────────────────────────
KB_CHUNK_SIZE=400                       # target tokens per chunk
KB_CHUNK_OVERLAP=80                     # overlap between adjacent chunks
KB_TOP_K=5                             # top results to retrieve per query

# ── Vector store (local, no Docker needed) ────────────────────
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_COLLECTION=darwix_kb
QDRANT_PATH=q2_knowledge_base/embeddings

# ── Database ──────────────────────────────────────────────────
DATABASE_URL=sqlite:///./darwix.db

# ── Q4 Nudge controls ─────────────────────────────────────────
NUDGE_CONFIDENCE_THRESHOLD=0.65
NUDGE_COOLDOWN_SECONDS=30
NUDGE_MAX_ACTIVE=5
STREAM_CHUNK_SECONDS=3

# ── App ───────────────────────────────────────────────────────
APP_ENV=development
APP_PORT=8000
LOG_LEVEL=INFO
SECRET_KEY=change-me-in-production
```

---

## 12. Submission Checklist

- [x] GitHub repository
- [x] README (this file)
- [x] `.env.example` (committed, no secrets)
- [x] No API keys committed to source control
- [x] No customer PII committed
- [x] Architecture diagram (section 2 of this README)
- [x] Setup instructions (section 4)
- [x] Sample data (`q2_knowledge_base/data/raw/health_insurance_source.json`)
- [x] Q1 voice agent working (WebSocket + browser UI)
- [x] Q1 call recordings / transcripts (3 calls in `docs/transcripts/`)
- [x] Q1 test call results documented (section 7)
- [x] Q2 KB pipeline working (ingest → embed → retrieve)
- [x] Q2 schema defined (`q2_knowledge_base/schema.py`)
- [x] Q2 retrieval evaluation (5 queries, `retrieval_test_results.md`)
- [x] Q2 source tracking (record_id, source, source_url, version on every result)
- [x] Q1 ↔ Q2 integration (agent queries KB before every LLM call)
- [x] Q3 Philippines bot (Taglish, fil-PH-BlessicaNeural TTS)
- [x] Q3 Indonesia bot (Bahasa Indonesia, id-ID-GadisNeural TTS)
- [x] Q3 call recordings / transcripts (2+2 calls in `docs/transcripts/`)
- [x] Q3 localization evidence (localization examples in `prompts_ph.py`, `prompts_id.py`, comparison table in section 9)
- [x] Q3 accent handling documented
- [x] Q4 real-time streaming pipeline
- [x] Q4 signal detection (rule-based + LLM, 9 signal types)
- [x] Q4 nudge engine
- [x] Q4 suppression (7 quality controls)
- [x] Q4 latency measurements (`latency_report.md`)
- [x] P50 latency (278ms rule / 748ms LLM / 490ms combined)
- [x] P95 latency (390ms rule / 1,240ms LLM / 960ms combined)
- [x] False-positive analysis (~5% FP rate on clean audio)
- [x] Q4 CLI demo (`python3 -m q4_live_insights.run_demo`)
- [x] Known limitations documented (section 13)
- [x] Production improvement plan documented (section 14)

---

## 13. Known Limitations

| Area | Limitation | Impact |
|---|---|---|
| Voice interface | Browser-only (WebSocket mic). No PSTN / telephone number. | Cannot dial out or receive real phone calls. Web calling only. |
| STT | Groq Whisper receives complete audio files, not true streaming. The browser accumulates audio until the user releases the mic button. | ~0.5–2s perceived latency on longer utterances. Not truly streaming in the ASR sense. |
| TTS | Edge-TTS requires outbound WSS connections to Microsoft servers. Will not work in fully air-gapped environments. | Requires network access. |
| Embeddings | Gemini embedding API has a free-tier rate limit. Ingesting large corpora may require retry backoff. | Ingestion of >100 documents may be slow. |
| LLM | `groq/compound-mini` has limited structured output / tool-calling support. Lead field extraction uses regex rather than LLM function calls. | May miss edge-case utterance patterns that fall outside the regex rules. |
| Knowledge base | Source data is synthetic/demo. Does not represent real Darwix or insurer policies. | All answers are grounded in demo data. Not suitable for production without real KB content. |
| Q3 Filipino TTS | `fil-PH-BlessicaNeural` is a high-quality Filipino voice but Taglish rhythm is not always natural for mixed-language utterances. | Some Taglish sentences may sound slightly accented or unnatural. Needs native-speaker review. |
| Q3 Indonesian accents | Regional Indonesian accents (Javanese, Sundanese, Batak) are detected via keyword heuristics only. No regional TTS available on Edge-TTS. | All Indonesian output uses standard Jakarta voice. Regional warmth is text-only. |
| Sessions | Conversation state is stored in-process (Python dict). Server restart loses active sessions. | Acceptable for prototype. Not suitable for multi-instance or long-lived production deployments. |
| Concurrency | Single-process FastAPI. Under load, LLM calls will queue and latency will increase. | Suitable for demo and evaluation. Not production-ready for concurrent call volumes. |

---

## 14. Production Improvement Plan

1. **Streaming STT with Deepgram Nova-2** — Replace the file-based Groq Whisper integration with Deepgram's real-time streaming ASR. This reduces per-word latency from ~400ms to ~50ms and enables true word-by-word signal detection. Deepgram also provides per-word confidence scores, enabling ASR-confidence-based nudge filtering to reduce false positives on noisy audio.

2. **Local multilingual embeddings** — Replace Gemini embeddings with a local `sentence-transformers` model (e.g. `paraphrase-multilingual-mpnet-base-v2`). This eliminates the embedding API rate limit, enables fully offline operation, and improves embedding quality for Tagalog and Bahasa Indonesia content.

3. **Upgrade to LLaMA 3.3 70B** — Replace `groq/compound-mini` with `llama-3.3-70b-versatile` on Groq (still free). Better instruction-following, richer conversational quality, and support for structured JSON output — enabling LLM-based lead field extraction to replace regex parsing.

4. **Twilio PSTN integration** — Add a Twilio inbound/outbound number so the agent can make and receive real phone calls. The FastAPI WebSocket server maps cleanly to a Twilio `<Stream>` webhook.

5. **Redis for distributed session state** — Replace in-process session dict with Redis. Enables horizontal scaling (multiple FastAPI workers), session persistence across restarts, and TTL-based session cleanup.

6. **Scheduled KB re-ingestion** — Add a cron/scheduler job to re-ingest the knowledge base when source documents change. Track document versions and only re-embed changed chunks to minimise API cost.

7. **ASR confidence filtering for Q4** — Add Deepgram word-level confidence to the signal detector. Skip LLM signal detection on chunks with mean word confidence below 0.70. This is the single highest-impact change for reducing false-positive nudges on noisy or accented calls.

8. **Native-speaker compliance review** — Before production deployment of Q3 bots, engage native Filipino and Indonesian speakers to review all Taglish and Bahasa scripts for natural language quality, cultural accuracy, and regulatory compliance. Insurance language in particular carries legal obligations that synthetic data and automated localization cannot fully satisfy.
