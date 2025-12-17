Module: src/agent/core/security.py
==================================

Responsibility
--------------
- Оценить предлагаемое действие на потенциальную разрушительность и решить, нужно ли подтверждение.

Key Components
--------------
- SecurityDecision: requires_confirmation (bool), reason (optional).
- Heuristics: ключевые слова (pay/buy/checkout/order/.../delete/remove/unsubscribe/transfer), card-like number pattern,
  чувствительные формы (name/id/aria-label), risky navigation (SENSITIVE_PATHS, RISKY_DOMAINS).
- _get_element_text: извлекает текст/role/tag по element_id из observation.
- _has_sensitive_form: сканирует mapping на “payment/account” формы.

Behavior
--------
- analyze_action(action, observation):
  - Навигационные действия (navigate/search/go_back/go_forward) проходят риск-оценку наравне с кликами/типингом.
  - Keyword/card/form/risky URL → requires_confirmation=True с reason.
  - Иначе respects action.requires_confirmation flag (если задан).
- prompt_confirmation(action, reason, auto_confirm=False): печатает reason/action; auto_confirm bypass; иначе спрашивает пользователя.

Settings/Env
------------
- SENSITIVE_PATHS (default: payment,checkout,billing,account/close,delete,unsubscribe)
- RISKY_DOMAINS (default: paypal,stripe,bank,billing,secure)
