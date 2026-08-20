# Q3 — Philippines vs Indonesia: Market Comparison

## Overview

| Dimension              | Philippines (PH)                            | Indonesia (ID)                                   |
|-----------------------|---------------------------------------------|--------------------------------------------------|
| Sector                | Life insurance / bancassurance              | Multifinance / consumer finance                  |
| Primary language      | Taglish (English + Filipino code-switching) | Bahasa Indonesia + finance English loanwords     |
| Formality register    | Semi-formal, warm, relational               | Formal for collections, colloquial for rapport   |
| Politeness system     | "po/ho" + "Sir/Ma'am"                       | "Bapak/Ibu" + "mohon" vs "tolong"               |
| Primary motivator     | Family protection (pamilya)                 | Practical affordability (cicilan masuk akal)     |
| Key cultural insight  | Bahala na mindset requires reframing        | Menjaga muka (face-saving) in collections       |
| Code-switching        | Heavy English mid-Tagalog sentence          | Finance loanwords (DP, tenor, cicilan) embedded  |
| Regional accents      | Relatively uniform (Manila-standard dominant) | Significant variation: Javanese, Sundanese, Batak |
| ASR model             | Deepgram nova-2-general (tl + en)           | Deepgram nova-2-general (id)                     |
| ASR quality (clean)   | ~88% accuracy, ~12% WER                     | ~89% Jakarta, ~83% Javanese, ~81% Sundanese      |
| TTS primary           | ElevenLabs Filipino-English voice           | ElevenLabs Indonesian female voice               |
| TTS fallback          | Google Cloud fil-PH-Standard-B              | Google Cloud id-ID-Wavenet-B                     |
| Regional TTS          | Not available — single Filipino voice       | Not available — Jakarta standard only            |

---

## Code-Switching Behavior Comparison

### Philippines
- Customers switch to English for financial terms AND for emphasis/emotion
- Example: "Gusto ko ng coverage for my family" — syntax is Tagalog, key noun is English
- Bot mirrors this naturally: "Ang Standard Plan po ay PHP 2,500 per month — that covers hospitalisation up to PHP 300,000"
- English financial terms spoken with Filipino prosody (not American accent)

### Indonesia
- Customers use English abbreviations embedded in Indonesian sentences
- Example: "DP-nya berapa?" (What's the DP?) — Bahasa sentence, English abbreviation
- English loanwords are fully integrated vocabulary, not code-switching per se
- Full English switch (e.g., "How much is the interest rate?") handled via Deepgram multi-language fallback

---

## Localization vs Translation Evidence

### Philippines — 3 Examples

**1. Premium objection:**
- Literal: "The plan costs PHP 1,200 per month."
- Localized: "Mas mura pa 'yan sa isang family dinner sa labas" — reframes cost in relatable PH context (family restaurant meal)

**2. Lapse reminder:**
- Literal: "Your policy will lapse if you don't pay."
- Localized: "Ayaw naman nating mag-lapse ang policy ninyo" — uses "natin" (our/we) instead of "your" — shared ownership

**3. Bahala-na reframe:**
- Literal: "Insurance protects your family."
- Localized: "Ang insurance po ay hindi para sa atin — para po ito sa mga taong mahal natin" — invokes Filipino family-centeredness

### Indonesia — 3 Examples

**1. Collections opener:**
- Literal: "Your payment is overdue. Penalty applies."
- Localized: "Supaya tidak ada denda tambahan... kita bisa cari solusi bersama" — face-saving, solution-oriented

**2. Javanese speaker:**
- Literal: "Do you want to proceed?"
- Localized: "Njeh Bapak, jadi apakah Bapak berminat untuk kita proses lebih lanjut..." — mirrors Javanese marker, reduces friction

**3. Nanti-dulu (soft refusal):**
- Literal: "Please decide soon."
- Localized: Respects pace, offers WhatsApp (Indonesia #1 channel), no pressure — preserves muka

---

## Fallback / Escalation Language Consistency

### Philippines
- Fallback stays in Taglish: "Ay, 'di ko po agad masasabi... Papaabot ko po kayo sa specialist"
- Escalation in Filipino: "Sige po, iko-connect ko na kayo sa aming specialist"
- No unexpected English switching during sensitive moments ✅

### Indonesia
- Fallback in formal Bahasa: "Mohon maaf, saya tidak memiliki informasi lengkap..."
- Escalation in polite Bahasa: "Baik Bapak/Ibu, saya akan langsung hubungkan..."
- Accent-aware: Javanese customers receive slightly softer phrasing ✅

---

## Known Native-Speaker / Compliance Gaps

### Philippines
- **TTS gap:** No native Tagalog TTS model in ElevenLabs. Filipino-English bilingual voice is used. Pure Tagalog phrases may have unnatural prosody.
- **GCash / e-wallet coverage:** Not in KB. Fallback triggered correctly but should be added.
- **Regional accents:** Cebuano (Bisaya), Ilocano speakers not tested. May degrade ASR quality by 8-12%.
- **Compliance:** "94% claims settlement" stat is in KB — if KB is updated, this auto-updates. ✅

### Indonesia
- **Regional TTS:** No Javanese/Sundanese/Batak TTS voices commercially available. Jakarta accent used universally — may feel impersonal to Javanese speakers.
- **Batak accent:** ~21% WER — recommend human review for high-value or collections calls.
- **Sharia/conventional finance:** Bot does not differentiate between conventional and sharia-compliant products. This is a significant gap for Muslim-majority markets in Indonesia.
- **Regulatory:** OJK (Otoritas Jasa Keuangan) disclosure requirements not explicitly scripted. Human review of compliance scripts recommended before production deployment.
