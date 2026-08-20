# Q3 Philippines — Call 01: Cooperative Customer (Taglish)
**Scenario:** Cooperative customer, natural Taglish, bancassurance cross-sell interest  
**Language:** Taglish (English + Filipino code-switching)  
**Bot:** Maya — ExampleInsurer Philippines Life Insurance  
**Outcome:** ✅ QUALIFIED  
**Turns:** 10  

---

**MAYA:** Magandang hapon po! Ito po si Maya mula sa ExampleInsurer Philippines. Tumatawag po kami para ibahagi ang aming pinakabagong life insurance plans na espesyal na designed para protektahan ang inyong pamilya. Mayroon po ba kayong dalawa o tatlong minuto?

**CUSTOMER:** Oh, sige po, okay lang.

**MAYA:** Salamat po! Para mairekomenda ko ang pinakamagandang plan para sa inyo — pwede ko po bang malaman ang inyong edad?

**CUSTOMER:** Tatlumpu't lima po ako.

**MAYA:** Ay, perfect age po 'yan para magsimula ng life insurance! Para sa sarili lang po ba ninyo, o for the family din?

**CUSTOMER:** Para sa amin ng asawa ko at yung dalawa naming bata.

**MAYA:** Maganda po 'yan — family coverage. Mayroon na po bang existing na insurance ang pamilya ninyo ngayon?

**CUSTOMER:** Wala pa po, actually gusto na naming mag-kuha kaso hindi pa kami sure kung alin.

**MAYA:** Naiintindihan ko po 'yan. Maraming options kaya confusing talaga. Roughly po, magkano ang comfortable ninyong budget per month para sa coverage?

**CUSTOMER:** Siguro mga PHP 2,500 to PHP 3,000 po per month.

**MAYA:** Okay po, that works well. Batay sa sinabi ninyo — 35 years old, may asawa at dalawang anak, budget na PHP 2,500 to 3,000 — palagay ko po ang aming Standard Life Plan ang pinaka-angkop para sa inyo. Kasama na po doon ang hospitalisation coverage hanggang PHP 300,000 per year, at maaaring i-add ang asawa at mga bata sa 60% ng base premium bawat isa. At po, ang pre-existing conditions ay covered na after 12 months ng policy.

**CUSTOMER:** Oh nice! Ano po yung ibang benepisyo?

**MAYA:** Kasama rin po ang outpatient consultations — up to 6 visits per year para makita ng doctor. At may 30-day free-look period po — kung hindi po kayo satisfied within 30 days, pwedeng i-refund ang premium. Hindi po kayo naka-lock in kung hindi ninyo gusto.

**CUSTOMER:** Paano po mag-claim kung may mangyari?

**MAYA:** Simple lang po! Mag-file kayo ng claim through our mobile app o tawagan ang 1-800-555-0100. Kailangan lang po ng medical certificate, itemized bill, at proof of payment. Kailangan i-submit within 60 days ng medical event. Yun lang po.

**CUSTOMER:** Okay po 'yan. Gusto ko na po siguro ituloy ito.

**MAYA:** Grabe, napakaganda pong desisyon 'yan para sa pamilya ninyo! Ipapa-reach out ko na po kayo sa aming specialist para sa full enrollment. Pwede ko po bang makuha ang inyong email at contact number?

**CUSTOMER:** Oo, ang email ko po ay reyes.family@gmail.com at number ko ay 09189876543.

**MAYA:** Perfect po! Tatawagan kayo ng aming specialist within 24 hours. Salamat po sa inyong oras at tiwala, Ma'am/Sir. Ingat po kayo! [QUALIFIED]

---

## Call Result

| Field              | Value                                      |
|-------------------|--------------------------------------------|
| Outcome           | QUALIFIED                                  |
| Plan              | Standard                                   |
| Age               | 35 (eligible)                              |
| Dependents        | Spouse + 2 children                        |
| Existing Coverage | None                                       |
| Budget            | PHP 2,500–3,000/mo                         |
| Contact           | 09189876543                                |
| Fallback Used     | No                                         |
| Escalation        | No                                         |

## Localization Quality Notes

| Feature | Observation |
|---------|-------------|
| Code-switching | Natural Taglish throughout — "That works well" embedded in Tagalog sentence |
| Politeness markers | "po" used consistently; "Ma'am/Sir" title used appropriately |
| Financial terms | "premium," "coverage," "pre-existing," "outpatient" used in English within Tagalog sentences |
| Cultural framing | Family (asawa, mga bata) foregrounded — "proteksyon para sa pamilya" |
| ASR behavior | "Tatlumpu't lima" (35) correctly mapped to integer age |
| TTS | ElevenLabs Filipino-English voice — natural Taglish prosody |
