"""
Qualification Logic
===================
Tracks the state of a lead qualification call and determines outcomes.

State machine:
  GREETING → QUALIFYING → OBJECTION_HANDLING → RECOMMENDING → CLOSING → DONE

Eligibility rules (sourced from KB / policy):
  - Age: 18–65
  - BMI > 40: requires underwriting (flag for specialist)
  - Smoker: eligible but 15% premium loading
  - Pre-existing: covered after 12 months on Standard/Premium; excluded on Basic
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, List, Literal
from datetime import datetime
import json


ConversationStage = Literal[
    "greeting",
    "qualifying",
    "objection_handling",
    "recommending",
    "closing",
    "escalated",
    "done",
]

OutcomeTag = Literal["QUALIFIED", "NOT_QUALIFIED", "FOLLOW_UP", "ESCALATE", "IN_PROGRESS"]

PLAN_RULES = {
    "Basic":    {"monthly_premium": 1200, "hosp_limit": 100_000,   "outpatient": False, "dental": False},
    "Standard": {"monthly_premium": 2500, "hosp_limit": 300_000,   "outpatient": True,  "dental": False},
    "Premium":  {"monthly_premium": 4800, "hosp_limit": 1_000_000, "outpatient": True,  "dental": True},
}

SMOKER_LOADING = 0.15  # 15% on base premium


@dataclass
class LeadProfile:
    """Accumulated customer information from the conversation."""

    session_id: str
    name: Optional[str] = None
    age: Optional[int] = None
    smoker: Optional[bool] = None
    has_preexisting: Optional[bool] = None
    bmi_over_40: Optional[bool] = None
    num_dependents: int = 0
    monthly_budget: Optional[int] = None  # PHP
    contact_number: Optional[str] = None
    email: Optional[str] = None
    callback_time: Optional[str] = None
    plan_interest: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_crm_dict(self) -> dict:
        """Serialize for CRM / webhook submission."""
        return {
            "session_id": self.session_id,
            "name": self.name,
            "age": self.age,
            "smoker": self.smoker,
            "has_preexisting_conditions": self.has_preexisting,
            "bmi_flag": self.bmi_over_40,
            "dependents": self.num_dependents,
            "monthly_budget_php": self.monthly_budget,
            "contact_number": self.contact_number,
            "email": self.email,
            "callback_time": self.callback_time,
            "plan_interest": self.plan_interest,
            "captured_at": self.created_at,
        }


@dataclass
class QualificationState:
    """Tracks the full state of a single qualification call."""

    session_id: str
    stage: ConversationStage = "greeting"
    outcome: OutcomeTag = "IN_PROGRESS"
    lead: LeadProfile = field(init=False)
    conversation_history: List[dict] = field(default_factory=list)
    escalation_requested: bool = False
    out_of_scope_count: int = 0
    objection_count: int = 0
    turns: int = 0

    def __post_init__(self):
        self.lead = LeadProfile(session_id=self.session_id)

    def add_turn(self, role: Literal["user", "assistant"], content: str) -> None:
        self.conversation_history.append({"role": role, "content": content})
        if role == "user":
            self.turns += 1

    def check_eligibility(self) -> tuple[bool, str]:
        """
        Returns (is_eligible, reason).
        Called when enough profile info is available.
        """
        if self.lead.age is not None:
            if self.lead.age < 18:
                return False, "Applicant is under 18 years old."
            if self.lead.age > 65:
                return False, "Applicant is over 65 years old."
        return True, "Eligible"

    def recommend_plan(self) -> Optional[str]:
        """
        Simple rule-based plan recommendation from budget and needs.
        Returns plan name or None if not enough info.
        """
        if self.lead.monthly_budget is None:
            return None

        budget = self.lead.monthly_budget
        smoker_adj = 1 + SMOKER_LOADING if self.lead.smoker else 1.0

        for plan_name in ["Premium", "Standard", "Basic"]:
            plan = PLAN_RULES[plan_name]
            effective_premium = plan["monthly_premium"] * smoker_adj
            if budget >= effective_premium:
                # If they have preexisting, steer away from Basic
                if plan_name == "Basic" and self.lead.has_preexisting:
                    continue
                return plan_name

        # Budget is very tight — suggest Basic even with preexisting, flag it
        return "Basic"

    def calculate_quote(self, plan_name: str) -> dict:
        """Returns a preliminary quote summary."""
        plan = PLAN_RULES.get(plan_name, PLAN_RULES["Basic"])
        base = plan["monthly_premium"]
        smoker_adj = SMOKER_LOADING if self.lead.smoker else 0
        smoker_amount = round(base * smoker_adj)
        per_dependent = round(base * 0.60)
        dependent_total = per_dependent * self.lead.num_dependents
        total_monthly = base + smoker_amount + dependent_total

        return {
            "plan": plan_name,
            "base_premium_php": base,
            "smoker_loading_php": smoker_amount,
            "dependent_premium_php": dependent_total,
            "num_dependents": self.lead.num_dependents,
            "estimated_monthly_total_php": total_monthly,
            "hospitalisation_limit_php": plan["hosp_limit"],
            "outpatient": plan["outpatient"],
            "dental": plan["dental"],
            "disclaimer": (
                "This is a preliminary estimate only. "
                "Final premium is subject to underwriting and full application."
            ),
        }

    def finalize_outcome(self) -> OutcomeTag:
        """Set and return the final outcome based on current state."""
        if self.escalation_requested:
            self.outcome = "ESCALATE"
        elif self.lead.age is not None:
            eligible, _ = self.check_eligibility()
            if not eligible:
                self.outcome = "NOT_QUALIFIED"
            elif self.lead.plan_interest or self.lead.contact_number:
                self.outcome = "QUALIFIED"
            else:
                self.outcome = "FOLLOW_UP"
        else:
            self.outcome = "FOLLOW_UP"
        return self.outcome

    def to_summary(self) -> str:
        """Human-readable call summary for CRM / supervisor review."""
        quote = None
        if self.lead.plan_interest:
            quote = self.calculate_quote(self.lead.plan_interest)

        summary_lines = [
            f"=== CALL SUMMARY ===",
            f"Session ID : {self.session_id}",
            f"Outcome    : {self.outcome}",
            f"Turns      : {self.turns}",
            f"",
            f"--- Lead Profile ---",
            f"Name       : {self.lead.name or 'Not captured'}",
            f"Age        : {self.lead.age or 'Not captured'}",
            f"Smoker     : {self.lead.smoker}",
            f"Pre-existing: {self.lead.has_preexisting}",
            f"Dependents : {self.lead.num_dependents}",
            f"Budget     : PHP {self.lead.monthly_budget or 'N/A'}/mo",
            f"Contact    : {self.lead.contact_number or 'Not captured'}",
            f"Email      : {self.lead.email or 'Not captured'}",
            f"Callback   : {self.lead.callback_time or 'Not set'}",
            f"Plan Interest: {self.lead.plan_interest or 'Undecided'}",
        ]
        if quote:
            summary_lines += [
                f"",
                f"--- Preliminary Quote ---",
                f"Base Premium : PHP {quote['base_premium_php']}/mo",
                f"Smoker Load  : PHP {quote['smoker_loading_php']}/mo",
                f"Dependents   : PHP {quote['dependent_premium_php']}/mo",
                f"TOTAL        : PHP {quote['estimated_monthly_total_php']}/mo",
                f"Hosp Limit   : PHP {quote['hospitalisation_limit_php']:,}",
                f"Disclaimer   : {quote['disclaimer']}",
            ]
        return "\n".join(summary_lines)
