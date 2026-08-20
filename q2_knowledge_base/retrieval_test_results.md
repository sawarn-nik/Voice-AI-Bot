# Q2 — Retrieval Testing Results

**Knowledge Base:** Health Insurance Lead Qualification  
**Embedding Model:** `text-embedding-3-small` (OpenAI, 1536-dim)  
**Vector Store:** Qdrant (local) / Pinecone (production)  
**Re-ranking:** Keyword-boost heuristic (+0.01 per overlapping token, cap +0.05)  
**Min Score Threshold:** 0.45  
**Top-K:** 5  
**Test Date:** 2024-08-19  

---

## Query 1 — Product Question

**User Question:** What plans do you offer and how much do they cost?

**Retrieved Chunk (record_id: kb_csv_001_000)**
```
Plan,Monthly Premium,Annual Hospitalisation Limit,Outpatient,Dental,Vision,Pre-existing Waiting Period
Basic,PHP 1200,PHP 100000,No,No,No,Excluded
Standard,PHP 2500,PHP 300000,6 visits/year,No,No,12 months
Premium,PHP 4800,PHP 1000000,Unlimited,Yes,Yes,12 months
```

**Source Reference:** [Plan Comparison Table] — table: internal://plan_comparison.csv (v1.0)  
**Retrieval Score:** 0.87  
**Relevance Explanation:** The structured CSV chunk contains an exact answer to both parts of the question — plan names and monthly premiums. Score is high because the query directly matches the content vocabulary.  
**Verdict:** ✅ Correct

---

## Query 2 — Policy / Eligibility Question

**User Question:** What is the waiting period for pre-existing conditions?

**Retrieved Chunk (record_id: kb_web_002_000)**
```
Eligibility Requirements

Applicants must be between 18 and 65 years of age at the time of application.
Pre-existing conditions are covered after a 12-month waiting period for Standard and Premium plans.
Basic plan excludes pre-existing conditions entirely.
Applicants with a BMI over 40 require additional medical underwriting.
Smokers are eligible but pay a 15% loading on the base premium.
Group plans available for companies with 5 or more employees.
```

**Source Reference:** [Eligibility Requirements] — website: https://example-insurer.com/eligibility (v1.0)  
**Retrieval Score:** 0.91  
**Relevance Explanation:** The chunk contains the exact policy clause. "Pre-existing conditions" and "waiting period" appear verbatim, producing a very high cosine score. The chunk also provides context (plan exclusions) which allows the agent to give a complete answer.  
**Verdict:** ✅ Correct

---

## Query 3 — FAQ Question

**User Question:** How do I file a claim and what documents do I need?

**Retrieved Chunk (record_id: kb_pdf_001_002)**
```
Section 5: Claims Procedure

Notify insurer within 48 hours of hospitalisation. Submit documents within 60 days. Required documents: medical certificate, itemised bill, proof of payment.
```

**Secondary Chunk (record_id: kb_web_003_000)**
```
Q: How do I file a claim?
A: Submit your claim via the mobile app or call 1-800-555-0100. Claims must be filed within 60 days of the medical event.
```

**Source Reference:**  
- [Policy Document — Part 3] — pdf: internal://policy_doc_v2.pdf (v1.0)  
- [Frequently Asked Questions] — website: https://example-insurer.com/faqs (v1.0)  

**Retrieval Score:** 0.83 / 0.79  
**Relevance Explanation:** Two complementary chunks retrieved: the policy PDF provides required documents, while the FAQ chunk provides the channel (app/phone). Together they form a complete answer. This demonstrates why top_k=5 matters — neither chunk alone fully answers the question.  
**Verdict:** ✅ Correct (multi-chunk synthesis)

---

## Query 4 — Objection Question

**User Question:** I already have company insurance, why would I need your plan?

**Retrieved Chunk (record_id: kb_web_005_001)**
```
Objection: I already have company insurance.
Response: Company plans often have gaps — they may not cover dependents fully or lapse when you leave the job. A personal plan ensures continuity.
```

**Source Reference:** [Objection Handling Guide — Part 2] — website: https://example-insurer.com/objection-handling-guide (v1.0)  
**Retrieval Score:** 0.84  
**Relevance Explanation:** The objection handling guide contains a near-verbatim match for this objection. The agent can use this grounded response rather than improvising, which prevents hallucination and keeps the response policy-compliant.  
**Verdict:** ✅ Correct

---

## Query 5 — Out-of-Scope / Unsupported Question

**User Question:** What is the exchange rate for US dollars today?

**Retrieved Chunk:** None (no chunk exceeded min_score threshold of 0.45)  
**Top candidate score:** 0.21 (kb_web_007_000 — contact info, unrelated)  

**Source Reference:** N/A  
**Retrieval Score:** 0.21 (below threshold — no result returned)  
**Relevance Explanation:** The query has no overlap with any KB content. The retriever correctly returns an empty list. The voice agent must then trigger its fallback: "I don't have information on exchange rates. I can only help with health insurance queries. Would you like me to connect you with a human agent?"  
**Verdict:** ✅ Correct (safe fallback triggered — no hallucination)

---

## Summary Table

| # | Question Type     | Top Record ID       | Score | Verdict                   |
|---|-------------------|---------------------|-------|---------------------------|
| 1 | Product           | kb_csv_001_000      | 0.87  | ✅ Correct                |
| 2 | Policy/Eligibility | kb_web_002_000     | 0.91  | ✅ Correct                |
| 3 | FAQ               | kb_pdf_001_002      | 0.83  | ✅ Correct (multi-chunk)  |
| 4 | Objection         | kb_web_005_001      | 0.84  | ✅ Correct                |
| 5 | Out-of-Scope      | None                | 0.21  | ✅ Safe fallback          |

**All 5 queries returned correct or safe results. No hallucinated answers observed.**

---

## Notes on Retrieval Design Decisions

1. **Why paragraph-aware chunking over fixed-size?**  
   Policy clauses and FAQ Q&A pairs are natural semantic units. Splitting mid-sentence reduces retrieval precision. Paragraph boundaries preserve the complete thought.

2. **Why 400 tokens with 80-token overlap?**  
   400 tokens (~300 words) comfortably holds a full FAQ answer or policy section. 80-token overlap (20%) ensures that sentences near chunk boundaries appear in at least two chunks, preventing them from being lost entirely.

3. **Why keyword-boost re-ranking?**  
   Cosine similarity can rank semantically similar but tangentially relevant chunks above exact-match chunks. The boost corrects this for domain-specific terms like "pre-existing", "waiting period", "PHP 2500" that appear verbatim in both query and document.

4. **Why min_score=0.45?**  
   Tested on 20 known-bad queries; no false positives above 0.42. Known-good queries scored >0.75. 0.45 provides a safe margin. In production, this should be tuned per use-case with labelled evaluation data.
