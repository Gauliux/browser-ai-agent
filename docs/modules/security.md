Module: src/agent/core/security.py
==================================

Responsibility
--------------
- Evaluate a proposed action for potential risk and decide whether confirmation is needed.

Key Components
--------------
- SecurityDecision: requires_confirmation (bool), reason (optional).
- Heuristics: keywords (pay/buy/checkout/order/.../delete/remove/unsubscribe/transfer), card-like number pattern, sensitive forms (name/id/aria-label), risky navigation (SENSITIVE_PATHS, RISKY_DOMAINS).
- _get_element_text: extracts text/role/tag by element_id from observation.
- _has_sensitive_form: scans mapping for "payment/account" forms.

Behavior
--------
- analyze_action(action, observation):
  - Navigational actions (navigate/search/go_back/go_forward) go through risk analysis same as click/type.
  - Keyword/card/form/risky URL → requires_confirmation=True with reason.
  - Otherwise respects action.requires_confirmation flag (if provided).
- prompt_confirmation(action, reason, auto_confirm=False): prints reason/action; auto_confirm bypass; otherwise asks the user.

Settings/Env
------------
- SENSITIVE_PATHS (default: payment,checkout,billing,account/close,delete,unsubscribe)
- RISKY_DOMAINS (default: paypal,stripe,bank,billing,secure)
