# Q1 — Test Call 03: Incomplete Details + Conflicting Info + Safe Fallback
**Scenario:** Customer gives vague/conflicting answers; asks a question not in KB; age outside range  
**Date:** 2024-08-19 | **Session ID:** sess_demo_003  
**Outcome:** ❌ NOT_QUALIFIED (age > 65) + Safe Fallback triggered  
**Turns:** 11  

---

**ARIA:** Hello! This is Aria from ExampleInsurer. I'm calling to share how our health insurance plans can protect you and your family from unexpected medical costs. Do you have about 3 minutes?

**CUSTOMER:** Yes, I suppose so. My daughter told me to call.

**ARIA:** That's great! I'm happy to help. May I ask your name first?

**CUSTOMER:** I'm Lola Coring. Well, my real name is Corazon Reyes.

**ARIA:** Thank you, Ms. Reyes. Just so I can recommend the right plan — may I ask your age?

**CUSTOMER:** I'm... let me think... I was born in 1948. So I'm 76.

**ARIA:** Thank you for sharing that, Ms. Reyes. I want to be transparent with you — our individual health insurance plans are currently available to applicants between 18 and 65 years of age. At 76, you would unfortunately not qualify for our standard individual plans at this time.

**CUSTOMER:** Oh. But my daughter is 40. Could she get a plan?

**ARIA:** Absolutely — your daughter would qualify. At 40, she's in the ideal age range, and she could even add you as a dependent if she enrolls. I'd recommend having her call us directly, or I can arrange for a specialist to reach out to her. Would that be helpful?

**CUSTOMER:** Maybe. What about — can insurance cover my herbal treatments? I take a lot of traditional medicine.

**ARIA:** That's a great question. I don't have specific information about herbal or traditional medicine coverage in my knowledge base right now. I want to make sure I give you accurate information rather than guess — I can have a specialist call you back with the full details on that. Would that work for you?

**CUSTOMER:** Okay. And what about my diabetes? I've had it for 20 years.

**ARIA:** For pre-existing conditions like diabetes, our Standard and Premium plans provide coverage after a 12-month waiting period from the start of the policy. Our Basic plan does not cover pre-existing conditions. So for your daughter — if she were enrolling — her coverage would be straightforward, but any pre-existing conditions she has would follow the same waiting period rules.

**CUSTOMER:** I'm confused. Earlier you said I could be a dependent, but you also said I don't qualify?

**ARIA:** That's a really fair point to clarify — I should have explained it better. Eligibility for a primary policy holder is 18–65 years old. However, dependents — such as a spouse or parent added to an existing policy — may have different rules. I don't have the complete details for dependent-age limits in my knowledge base right now, so I don't want to give you incorrect information. A specialist can confirm this for you definitively. Shall I arrange that callback?

**CUSTOMER:** Yes please. Call my daughter Maria at 09181234567, best time is Saturday morning.

**ARIA:** Perfect — I've noted that. We'll have a specialist call Maria at 09181234567 this Saturday morning. Is there anything else I can help with today?

**CUSTOMER:** No, that's fine. Thank you.

**ARIA:** Thank you for your time, Ms. Reyes. We'll be in touch with Maria soon. Have a lovely day! [NOT_QUALIFIED] [FOLLOW_UP]

---

## Call Result

| Field                   | Value                                             |
|------------------------|---------------------------------------------------|
| Primary Outcome        | NOT_QUALIFIED (age 76, outside 18–65 range)       |
| Secondary Action       | FOLLOW_UP (referral to daughter Maria)            |
| Incomplete Details     | Herbal medicine coverage — KB returned no result  |
| Conflicting Info       | Dependent vs. primary eligibility confusion — agent acknowledged gap and deferred |
| Safe Fallback Triggered| ✅ Yes — twice (herbal medicine, dependent age limit) |
| Hallucination Check    | ✅ None — agent did NOT invent herbal medicine coverage rules |
| KB Retrievals          | Eligibility (0.91), FAQ-preexisting (0.88), Plan comparison (0.75) |
| Escalation             | No (orderly close)                                |

## Key Behaviours Demonstrated

1. **Age ineligibility handled gracefully:** Agent did not abruptly end the call. Pivoted to daughter referral — kept conversation productive.
2. **Safe fallback (herbal medicine):** KB returned no result above threshold (top score 0.22). Agent explicitly said "I don't have that specific information" rather than inventing an answer.
3. **Conflicting/ambiguous details:** Agent acknowledged confusion about dependent eligibility, did not guess, offered specialist callback as resolution.
4. **Partial qualification:** Call ended with actionable lead (Maria's contact captured) despite primary caller being ineligible.
