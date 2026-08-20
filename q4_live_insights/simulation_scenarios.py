"""
Simulation Scenarios
=====================
Pre-built call transcripts for testing all required signal types.
These replay at real-time speed via the pipeline's simulation mode.

Required test coverage (from assessment):
  ✅ Missed cross-sell opportunity
  ✅ Skipped disclosure / risky statement
  ✅ Rising frustration
  ✅ Noisy/ambiguous call (unnecessary nudges should be suppressed)
"""

from __future__ import annotations
from typing import List, Dict


def get_scenario(name: str) -> List[dict]:
    return SCENARIOS[name]


# ---------------------------------------------------------------------------
# Scenario 1: Missed cross-sell opportunity
# ---------------------------------------------------------------------------

SCENARIO_MISSED_CROSS_SELL: List[dict] = [
    {"speaker": "agent",    "text": "Hello, this is Aria from ExampleInsurer. Is now a good time?", "delay_s": 0},
    {"speaker": "customer", "text": "Sure, go ahead.", "delay_s": 2.0},
    {"speaker": "agent",    "text": "Great. I'm calling to help you find the right health insurance plan. May I ask your age?", "delay_s": 1.5},
    {"speaker": "customer", "text": "I'm 38.", "delay_s": 2.0},
    {"speaker": "agent",    "text": "Perfect. Are you looking for individual coverage or family?", "delay_s": 1.5},
    {"speaker": "customer", "text": "For me and my wife. Oh, and we also just bought a second car last month so life's been expensive.", "delay_s": 3.0},
    # ↑ SIGNAL: missed_cross_sell — "second car" should trigger multi-vehicle offer nudge
    {"speaker": "agent",    "text": "Understood, family coverage. Do you have any pre-existing conditions?", "delay_s": 2.0},
    # ↑ Agent ignored the cross-sell cue — compliance gap in missing disclosure still pending
    {"speaker": "customer", "text": "No, we're both healthy.", "delay_s": 2.5},
    {"speaker": "agent",    "text": "Great. And do you have a monthly budget in mind?", "delay_s": 1.5},
    {"speaker": "customer", "text": "Around PHP 4,000 to PHP 5,000 for everything.", "delay_s": 2.5},
    {"speaker": "agent",    "text": "Our Premium Plan at PHP 4,800 would be a great fit. It covers hospitalisation up to PHP 1 million, plus dental and vision.", "delay_s": 2.5},
    # ↑ SIGNAL: compliance_gap — agent pitched plan without mentioning waiting period / exclusions
    {"speaker": "customer", "text": "Sounds great, I'd like to sign up.", "delay_s": 3.0},
    # ↑ SIGNAL: buying_signal
    {"speaker": "agent",    "text": "Wonderful! Let me take down your details.", "delay_s": 1.5},
]


# ---------------------------------------------------------------------------
# Scenario 2: Compliance gap / risky statement
# ---------------------------------------------------------------------------

SCENARIO_COMPLIANCE_GAP: List[dict] = [
    {"speaker": "agent",    "text": "Hi, I'm calling from ExampleInsurer. We have a great health plan for you.", "delay_s": 0},
    {"speaker": "customer", "text": "What kind of plan?", "delay_s": 2.0},
    {"speaker": "agent",    "text": "It's our Premium Plan. Covers absolutely everything — hospitalisation, outpatient, dental, vision.", "delay_s": 2.0},
    # ↑ SIGNAL: compliance_gap — "covers absolutely everything" is a false guarantee
    {"speaker": "customer", "text": "Even my diabetes treatment?", "delay_s": 2.5},
    {"speaker": "agent",    "text": "Yes, I guarantee this plan will cover all your medical needs. You'll definitely be approved.", "delay_s": 2.0},
    # ↑ SIGNAL: compliance_gap (HIGH confidence) — "I guarantee", "definitely approved" are prohibited claims
    {"speaker": "customer", "text": "And there's no waiting period right?", "delay_s": 2.5},
    {"speaker": "agent",    "text": "No waiting period, you're covered from day one for everything.", "delay_s": 2.0},
    # ↑ SIGNAL: compliance_gap — "no waiting period" is factually incorrect per policy
    {"speaker": "customer", "text": "Okay, that sounds perfect.", "delay_s": 2.5},
    {"speaker": "agent",    "text": "Great, let me get your details.", "delay_s": 1.5},
]


# ---------------------------------------------------------------------------
# Scenario 3: Rising frustration
# ---------------------------------------------------------------------------

SCENARIO_RISING_FRUSTRATION: List[dict] = [
    {"speaker": "agent",    "text": "Hello, this is Aria from ExampleInsurer. How are you today?", "delay_s": 0},
    {"speaker": "customer", "text": "Not great honestly. I've been trying to get a callback for three days.", "delay_s": 2.5},
    {"speaker": "agent",    "text": "I apologize for the wait. Can I take down your details?", "delay_s": 2.0},
    {"speaker": "customer", "text": "Every time I call I get a different agent who asks me the same questions. This is really frustrating.", "delay_s": 3.0},
    # ↑ SIGNAL: rising_frustration
    {"speaker": "agent",    "text": "I understand. Let me start from scratch — what plan were you interested in?", "delay_s": 2.0},
    {"speaker": "customer", "text": "I already told the last three agents — the Standard Plan. I just need to know if my condition is covered.", "delay_s": 3.0},
    # ↑ SIGNAL: rising_frustration (escalating — repetition + tone)
    {"speaker": "agent",    "text": "Right, the Standard Plan. And what condition did you want to check?", "delay_s": 2.0},
    {"speaker": "customer", "text": "This is ridiculous. Why can't anyone just look at my previous calls? I want to speak to a manager.", "delay_s": 3.0},
    # ↑ SIGNAL: escalation_risk + rising_frustration (HIGH priority)
    {"speaker": "agent",    "text": "I'll transfer you right now. Please hold.", "delay_s": 2.0},
]


# ---------------------------------------------------------------------------
# Scenario 4: Noisy/ambiguous call (nudges should be suppressed)
# ---------------------------------------------------------------------------

SCENARIO_NOISY_AMBIGUOUS: List[dict] = [
    {"speaker": "agent",    "text": "Hello this is Aria, can you hear me okay?", "delay_s": 0},
    {"speaker": "customer", "text": "Yes hello yes I can hear.", "delay_s": 2.0},
    # Short utterance — should NOT trigger LLM analysis
    {"speaker": "agent",    "text": "Great. I'm calling about our health insurance plans.", "delay_s": 1.5},
    {"speaker": "customer", "text": "Hmm okay.", "delay_s": 2.0},
    # Too short — no signal
    {"speaker": "agent",    "text": "Do you currently have any health coverage?", "delay_s": 2.0},
    {"speaker": "customer", "text": "Maybe, I think so, not sure.", "delay_s": 2.5},
    # Ambiguous — should not generate a confident signal
    {"speaker": "agent",    "text": "Okay. And are you interested in learning more?", "delay_s": 2.0},
    {"speaker": "customer", "text": "I suppose... maybe... let me think.", "delay_s": 3.0},
    # Weak engagement — not a buying signal, not a rejection — should suppress low-value nudge
    {"speaker": "agent",    "text": "Of course, take your time. Can I call you back at a better time?", "delay_s": 2.0},
    {"speaker": "customer", "text": "Sure, maybe next week.", "delay_s": 2.5},
    # SIGNAL: callback_request (should fire — clear and above threshold)
    {"speaker": "agent",    "text": "Perfect, I'll note that down.", "delay_s": 1.5},
]


SCENARIOS: Dict[str, List[dict]] = {
    "missed_cross_sell":    SCENARIO_MISSED_CROSS_SELL,
    "compliance_gap":       SCENARIO_COMPLIANCE_GAP,
    "rising_frustration":   SCENARIO_RISING_FRUSTRATION,
    "noisy_ambiguous":      SCENARIO_NOISY_AMBIGUOUS,
}
