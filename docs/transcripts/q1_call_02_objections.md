# Q1 — Test Call 02: Objections + Out-of-Scope + Human Escalation
**Scenario:** Customer raises multiple objections, asks an out-of-scope question, then requests human  
**Date:** 2024-08-19 | **Session ID:** sess_demo_002  
**Outcome:** 🔄 ESCALATE → Human Agent  
**Turns:** 12  

---

**ARIA:** Hello! This is Aria from ExampleInsurer. I'm calling to share how our health insurance plans can protect you and your family from unexpected medical costs. Do you have about 3 minutes?

**CUSTOMER:** Look, I'm really busy. Make it quick.

**ARIA:** Of course — I'll be brief. We have plans starting at just PHP 1,200 a month, which is less than PHP 40 a day for hospitalisation coverage up to PHP 100,000. Can I ask — do you currently have any health insurance?

**CUSTOMER:** I already have insurance through my company. I don't need another one.

**ARIA:** That's actually very common, and it's a good point to raise. Company plans often have gaps — they may not fully cover your dependents, and they can lapse when you change jobs or retire. A personal plan ensures your coverage stays with you regardless of employment. Would that kind of continuity be useful for you?

**CUSTOMER:** I guess I hadn't thought of it that way. But it's expensive.

**ARIA:** I understand — budget is always important. Our Basic Plan starts at PHP 1,200 per month, which covers hospitalisation up to PHP 100,000. That could easily offset the cost of a single hospital stay. And you can always upgrade later as your needs change.

**CUSTOMER:** Okay, but honestly I don't really trust insurance companies. You take premiums for years and then fight every claim.

**ARIA:** That's a fair concern, and I won't dismiss it. ExampleInsurer is regulated by the Insurance Commission and had a 94% claims settlement ratio in 2023 — meaning nearly all valid claims were paid. We also have a 60-day claims submission window and a dedicated claims team reachable at 1-800-555-0100.

**CUSTOMER:** Hmm. By the way, what's the stock price of ExampleInsurer right now?

**ARIA:** That's outside what I can help with today — I'm only set up for health insurance queries. But I'd be happy to keep helping you find the right plan. Shall we continue?

**CUSTOMER:** Fine. What happens if I get diagnosed with something after I sign up?

**ARIA:** Any new condition diagnosed after your policy starts is covered immediately, with no waiting period. Pre-existing conditions — things you already have before signing up — are covered after a 12-month waiting period on our Standard and Premium plans. Our Basic plan excludes pre-existing conditions entirely.

**CUSTOMER:** And what if I'm not happy and want a refund?

**ARIA:** All plans include a 30-day free-look period from the date of issuance. If you cancel within those 30 days, you get a full refund minus a small administrative fee. After that, premiums are not refundable, though you can cancel the policy going forward at any time.

**CUSTOMER:** This is getting complicated. I want to talk to a real person.

**ARIA:** Of course — let me connect you to one of our specialists right away. Please hold for a moment. [ESCALATE]

---

## Call Result

| Field               | Value                                       |
|--------------------|---------------------------------------------|
| Outcome            | ESCALATE                                    |
| Objections Handled | 3 (company insurance, cost, trust)          |
| Out-of-Scope       | 1 (stock price) — correctly deflected       |
| Escalation Trigger | Explicit human request                      |
| KB Retrievals      | Objections (0.84), Policy exclusions (0.88), FAQ-refund (0.81) |
| Fallback Used      | No (all answers found in KB)                |
| Hallucination      | None — all stats (94% settlement, 60-day window) sourced from KB |

## Key Behaviours Demonstrated

1. **Objection handling (KB-grounded):** All three objections resolved using retrieved content from the objection handling guide. No improvised statistics.
2. **Out-of-scope deflection:** Stock price question correctly identified as outside scope. Agent did not attempt an answer or apologise excessively.
3. **Human escalation:** Immediate, graceful handoff on explicit human request. No resistance or delay.
4. **Safe fallback not triggered** because the KB contained answers to all insurance questions asked.
