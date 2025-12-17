from __future__ import annotations

import re
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from agent.core.observe import Observation


_DESTRUCTIVE_KEYWORDS = re.compile(
    r"(pay|buy|checkout|order|confirm payment|card|cvv|delete|remove|unsubscribe|transfer|ssn|social security|bank account)",
    re.IGNORECASE,
)
_CARD_PATTERN = re.compile(r"\b\d{13,19}\b")
_SENSITIVE_PATHS_ENV = os.getenv("SENSITIVE_PATHS", "payment,checkout,billing,account/close,delete,unsubscribe")
_RISKY_DOMAINS_ENV = os.getenv("RISKY_DOMAINS", "paypal,stripe,bank,billing,secure")
_SENSITIVE_PATHS = re.compile("|".join([re.escape(x.strip()) for x in _SENSITIVE_PATHS_ENV.split(",") if x.strip()]), re.IGNORECASE)
_RISKY_DOMAINS = re.compile("|".join([re.escape(x.strip()) for x in _RISKY_DOMAINS_ENV.split(",") if x.strip()]), re.IGNORECASE)


@dataclass
class SecurityDecision:
    requires_confirmation: bool
    reason: Optional[str]


def _get_element_text(observation: Observation, element_id: Optional[int]) -> str:
    if element_id is None:
        return ""
    for el in observation.mapping:
        if el.id == element_id:
            return (el.text or "") + " " + (el.role or "") + " " + (el.tag or "")
    return ""


def _has_sensitive_form(observation: Observation) -> bool:
    for el in observation.mapping:
        text = (el.text or "").lower()
        role = (el.role or "").lower() if el.role else ""
        tag = (el.tag or "").lower()
        # Limit scan to form-like elements to avoid false positives on nav/tabs.
        is_form_control = tag in {"input", "textarea", "select", "form"} or role in {"input", "textbox", "combobox", "searchbox"}
        if not is_form_control:
            continue
        attr_texts = [text]
        if getattr(el, "attr_name", None):
            attr_texts.append(str(el.attr_name).lower())
        if getattr(el, "attr_id", None):
            attr_texts.append(str(el.attr_id).lower())
        if getattr(el, "aria_label", None):
            attr_texts.append(str(el.aria_label).lower())
        combined = " ".join(attr_texts)
        sensitive_tokens = ["card", "cc", "cvv", "billing", "payment", "ssn", "passport", "account", "email"]
        if any(k in combined for k in sensitive_tokens):
            return True
    return False


def analyze_action(action: Dict[str, Any], observation: Observation) -> SecurityDecision:
    action_type = action.get("action")
    value = action.get("value") or ""
    element_id = action.get("element_id")

    # Ask/Done are non-destructive by design.
    if action_type in {"ask_user", "done"}:
        return SecurityDecision(False, None)

    element_text = _get_element_text(observation, element_id)
    combined_text = f"{value} {element_text}".strip()

    # Keyword-based heuristics.
    if _DESTRUCTIVE_KEYWORDS.search(combined_text):
        return SecurityDecision(True, "Matched destructive keyword.")

    # Card-like input when typing.
    if action_type == "type" and _CARD_PATTERN.search(value.replace(" ", "")):
        return SecurityDecision(True, "Value looks like a card number.")

    # Sensitive forms on page.
    if _has_sensitive_form(observation):
        return SecurityDecision(True, "Sensitive form detected on page.")

    # Sensitive paths/domains for navigation/history/search flows.
    if action_type in {"navigate", "search", "go_back", "go_forward"}:
        target_url = str(value).lower()
        if _SENSITIVE_PATHS.search(target_url) or _RISKY_DOMAINS.search(target_url):
            return SecurityDecision(True, "Navigation to risky domain/path.")

    return SecurityDecision(bool(action.get("requires_confirmation")), None)


def prompt_confirmation(action: Dict[str, Any], reason: Optional[str], *, auto_confirm: bool = False) -> bool:
    print("[confirm] Potentially destructive action detected.")
    if reason:
        print(f"[confirm] Reason: {reason}")
    print(f"[confirm] Proposed action: {action}")
    if auto_confirm:
        print("[confirm] Auto-confirm enabled; proceeding without prompt.")
        return True
    reply = input("[confirm] Proceed? (y/N): ").strip().lower()
    return reply in {"y", "yes"}
