Module: src/agent/security.py
=============================

Responsibility
--------------
- Evaluate proposed action for potential destructiveness and decide on confirmation.

Key Components
--------------
- SecurityDecision: requires_confirmation (bool), reason (optional).
- Destructive heuristics: regex keywords (pay/buy/checkout/order/confirm payment/card/cvv/delete/remove/unsubscribe/transfer/ssn/bank account), card-like number pattern, sensitive forms (name/id/aria-label containing card/cc/cvv/billing/payment/ssn/passport/account/email), risky navigation (SENSITIVE_PATHS, RISKY_DOMAINS env lists).
- _get_element_text: fetch text/role/tag by element_id from observation.
- _has_sensitive_form: scan mapping for sensitive form controls.

Behavior
--------
- analyze_action(action, observation):
  - Meta actions (ask_user/done/navigate/go_back/go_forward/search) → non-destructive by default (navigate still checked for risky domains/paths).
  - Keyword match or card pattern or sensitive form → requires_confirmation True with reason.
  - Otherwise respect action.requires_confirmation flag.
- prompt_confirmation(action, reason, auto_confirm=False): prints reason/action; auto_confirm bypasses prompt; otherwise asks user.

Settings/Env
------------
- SENSITIVE_PATHS (default payment,checkout,billing,account/close,delete,unsubscribe), RISKY_DOMAINS (paypal,stripe,bank,billing,secure).
- auto_confirm flag handled by callers.
