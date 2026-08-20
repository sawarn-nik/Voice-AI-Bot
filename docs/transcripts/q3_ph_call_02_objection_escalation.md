# Q3 Philippines — Call 02: Sector Objection + Colloquial Speech + Escalation
**Scenario:** Customer uses colloquial Filipino, raises "bahala na" mindset, mixed English finance terms, then requests human  
**Language:** Taglish — heavier Tagalog, colloquial register  
**Bot:** Maya — ExampleInsurer Philippines Life Insurance  
**Outcome:** 🔄 ESCALATE → Human Specialist  
**Turns:** 11  

---

**MAYA:** Magandang umaga po! Ito po si Maya mula sa ExampleInsurer Philippines. Tumatawag po kami para ibahagi ang aming pinakabagong life insurance plans na espesyal na designed para protektahan ang inyong pamilya. Mayroon po ba kayong dalawa o tatlong minuto?

**CUSTOMER:** Ay nako, insurance nanaman. Okay sige, anong meron?

**MAYA:** Ay, pasensya na po kung busy kayo! Maikli lang naman ito. Basta alam ninyo po na naghahanap kami ng paraan para masigurado na protektado ang pamilya ninyo sa hindi inaasahang gastos sa ospital o kung ano mang mangyari. May interest po ba kayo na malaman kung magkano?

**CUSTOMER:** Ay basta, bahala na 'yan. Healthy naman ako eh, hindi ko pa kailangan 'yan.

**MAYA:** Naiintindihan ko po 'yung feeling na 'bahala na, basta mabuhay tayo.' Pero Sir/Ma'am, ang insurance po ay hindi talaga para sa atin — para po ito sa mga taong mahal natin. Para hindi po sila mahirapan kung may mangyari. Kahit maliit na coverage, malaking bagay po 'yun sa pamilya. May mga anak o asawa po ba kayong depende sa inyo?

**CUSTOMER:** Meron, dalawang anak. Pero sabi ko okay na 'yan, bata pa ako.

**MAYA:** Actually po Sir/Ma'am, karamihan sa aming mga claims ay nanggagaling sa mga miyembro na 25 to 40 years old — mostly para sa accidents at sudden illnesses. At ang pinaka-mababang premium ay makukuha ninyo ngayong healthy pa kayo. Mas mahal po ang mag-apply kapag may sakit na. Parang locking in a low rate ngayon habang bata pa.

**CUSTOMER:** Ay oo nga. Pero 'yung mga insurance kasi, bayad ka ng bayad tapos ayaw naman mag-settle ng claims.

**MAYA:** Legit na concern po 'yan, at hindi ko po ito basta-basta isasantabi. ExampleInsurer po ay regulated ng Insurance Commission, at 94% ng aming valid claims ay na-settle noong 2023. Meron din kaming dedicated claims team na pwedeng tawagan 24/7. Hindi po kami nag-e-escape sa valid claims.

**CUSTOMER:** 94% lang? Ibig sabihin may 6% na hindi naibayad?

**MAYA:** Tama po ang observation ninyo. 'Yung 6% po ay karamihan ay claims na hindi naka-meet ng dokumentasyon requirements — hindi dahil ayaw namin bayaran. Kaya rin po kaya mahalaga na talagang i-file ang claim within 60 days at kumpleto ang documents: medical certificate, itemized bill, at proof of payment.

**CUSTOMER:** Hmm. Saan pwede mag-bayad ng premium? GCash ba?

**MAYA:** Ay, 'di ko po agad masasabi ang exact details ng payment channels namin. Papaabot ko po kayo sa aming specialist para ma-confirm — okay lang po ba? Siguradong meron pong convenient options para sa inyo.

**CUSTOMER:** Sige, pero gusto ko na makausap yung actual na tao, hindi automated.

**MAYA:** Sige po, iko-connect ko na kayo sa aming specialist. Sandali lang po. [ESCALATE]

---

## Call Result

| Field                    | Value                                               |
|-------------------------|-----------------------------------------------------|
| Outcome                 | ESCALATE                                            |
| Objections Handled      | 3 (bahala-na, age/health, trust in claims)          |
| Fallback Used           | ✅ Yes — GCash/payment channels not in KB           |
| Escalation Trigger      | Explicit human request ("actual na tao")            |
| Language Register       | Heavy colloquial — "Ay nako," "basta," "eh" used   |
| "Bahala na" Handling    | ✅ Acknowledged by name, reframed as family gift     |

## Localization Quality Notes

| Feature | Observation |
|---------|-------------|
| Colloquial speech | "Ay nako," "basta 'yan," "locking in" handled naturally |
| "Bahala na" mindset | Bot used the phrase explicitly and reframed culturally |
| 94% stats | Sourced from KB objection-handling guide — not invented |
| Safe fallback | GCash question correctly triggered fallback (not in KB) |
| Escalation language | "Actual na tao" — colloquial PH phrase for human agent, correctly caught |
| Politeness maintained | Never became defensive; maintained "po" throughout even under objection |

## Known Gaps
- GCash and digital payment channel details should be added to the KB for PH market
- "6% not settled" counter-objection was handled well but requires policy knowledge
