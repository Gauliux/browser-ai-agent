## Plan B: StrategyProfile as a layer of tolerance, context, and interpretation

(no action control, no domain logic in code)

---

## I. Core idea (definitions)

**StrategyProfile** is a *declarative execution profile* that:

- is **NOT** a decision-making strategy
- does **NOT** control agent actions
- does **NOT** analyze the runtime environment
- does **NOT** react to DOM / URL / mapping / candidates
- does **NOT** change dynamically within a single graph execution

StrategyProfile lives **outside core logic** and is applied as a *set of parameters and context* used:

- before the graph starts,
- and for post-interpretation of the result.

### StrategyProfile may ONLY:
1. set *tolerances* (budgets / thresholds),
2. add *declarative textual context* for the planner,
3. override *allowed_actions* (once, before start),
4. interpret the result (UX, explanations).

---

## II. Global constraints (the law of Plan B)

These constraints are **absolute**. Violating any point = **Plan B degrades into Plan A**.

### II.1. Absolutely forbidden

StrategyProfile **MUST NOT**:

- add **code-level site-specific conditions**  
  *(if hostname == ..., if url contains ...)*  
- analyze DOM, mapping, candidates, page text  
- read or interpret runtime signals  
- influence the choice of the next action (directly or indirectly)  
- change allowed_actions **during execution**  
- change stop_reason enum or introduce new terminal states  
- add new FSM stages, nodes, or graph transitions  
- change the order/logic of existing nodes  
- influence scorer, confidence, commit-path  
- contain rules like **“if X → do Y”**

**Key invariant:**  
StrategyProfile never knows or checks **what the agent “sees” or “found.”**

---

## III. Application model (critical)

### III.1. When it applies
- Profile applies **ONLY at the start of a new graph execution**.
- All profile parameters are **constant** within one run.

Forbidden:
- changing the profile mid-run
- “adapting” the profile during the graph

### III.2. Manual switching (allowed)
- Switching is allowed **between user requests** without restarting the runtime.
- New request → new graph → new StrategyProfile.

---

## IV. Defaults model

Decision:
- Parameters exist by default *without* a profile.
- StrategyProfile is an override on top of DefaultSettings.

Reasons:
- universal agent is first-class,
- profile is optional,
- no profile = stable, expected behavior,
- profile can be partial/incomplete.

Rule:
```
EffectiveSettings = DefaultSettings + overrides from StrategyProfile
```
If a field is absent in the profile → use default.

---

## V. StrategyProfile contract (no code)

StrategyProfile may contain **ONLY** the groups below.

### V.1. Budgets / tolerance (allowed)
- May override: max_no_progress_steps, max_steps, max_planner_calls, max_auto_scrolls, other **existing** budgets.

Constraints:
- no new counters,
- no conditional budgets in code (“if listing then ...”).

Allowed:
- *textual expectations* for the planner prompt (not code logic).

### V.2. Allowed actions (allowed, strict bounds)
- May directly override allowed_actions.

Rules:
- override happens **once before graph start**,
- final list must be a **subset of globally allowed actions**.

Forbidden:
- changing allowed_actions dynamically,
- changing allowed_actions depending on page/DOM.

> Allowed_actions is a permission profile, not a behavior strategy.

### V.3. Planner prompt parameterization (allowed, declarative only)
- May add context describing the **expected class of environment**; provides **semantic framing**, not an algorithm.

Allowed:
- declarative environment descriptions (“marketplace,” “typical goal is find/compare/add to cart”),
- expected page artifacts as text only (search, cards, cart, filters),
- override of existing textual flags: task_mode, explore_mode, avoid_search, listing_detected,
- naming specific platforms as a **class of environment** (e.g., “Ozon, Amazon, Yandex Market”) **WITHOUT code if/else**.

Forbidden:
- changing JSON schema,
- changing function calling format,
- changing plan format,
- adding step-by-step instructions,
- telling what to do first,
- turning the prompt into an alternative planner.

Formula:  
StrategyProfile may **describe the world**, but not **teach planning**.

### V.4. UX and result interpretation (allowed)
- May set a dictionary for terminal_reason interpretation,
- may set UX-summary style,
- may add a “human-friendly explanation” of completion.

Constraints:
- UX interpretation does not affect stop_reason,
- UX cannot change the fact of termination,
- UX cannot initiate new actions.

---

## VI. What StrategyProfile must never do (short law)

StrategyProfile **CANNOT**:
- control actions,
- analyze the page,
- react to the environment,
- change graph flow,
- influence commit,
- contain domain if/else,
- be an alternative planner,
- be a hidden observe.

**Core principle:**  
StrategyProfile describes expectations, but does not verify reality.

---

## VII. Minimal implementation order
1. Fix DefaultSettings as the source of truth.
2. Introduce StrategyProfile as an override object.
3. Apply profile **before** GraphState creation.
4. Wire profile to:
   - budgets,
   - allowed_actions,
   - planner prompt (context only).
5. Wire profile to UX-summary.
6. Add manual profile selection:
   - per user request,
   - without runtime restart.

---

## VIII. Success criteria
Plan B is done when:
- the universal agent works without a profile,
- profile is selected manually,
- profile changes only tolerance and context,
- core has no domain if/else,
- StrategyProfile can be removed without breaking the system,
- architecture remains transparent and auditable.
