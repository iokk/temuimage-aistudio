# Design

## Source of truth
- Status: Active
- Last refreshed: 2026-07-27
- Primary product surfaces: Streamlit sidebar navigation, provider settings, system settings, image/title workflows
- Evidence reviewed: `app.py`, `README.md`, `DEPLOYMENT.md`, current local browser page

## Brand
- Personality: focused, trustworthy, practical, and lightweight for repeated operations
- Trust signals: explicit provider status, visible model source, clear save/apply feedback, local-first data handling
- Avoid: marketing-style hero layouts, hidden destructive actions, ambiguous global defaults, and duplicated connection controls

## Product goals
- Goals: let operators configure several providers, discover upstream models, bind models by capability, and tune runtime limits without hunting through unrelated settings
- Non-goals: redesign the generation workflows or introduce a second frontend framework
- Success signals: a provider can be added, fetched, assigned title/vision/image models, tested, and saved from one provider card; system settings expose execution controls only

## Personas and jobs
- Primary personas: solo operators and small teams running a private image-generation workbench
- User jobs: switch providers safely, understand which upstream model will be used, and control queue/concurrency behavior
- Key contexts of use: local desktop browser, occasional relay/OpenAI-compatible endpoints, slow or intermittent upstream networks

## Information architecture
- Primary navigation: workflow pages first; provider settings for credentials, model discovery, model bindings, and connection testing; system settings for runtime behavior; templates/project center remain separate
- Core routes/screens: smart generation, quick generation/translation, title generation, provider settings, system settings
- Content hierarchy: page purpose -> current provider/status -> grouped controls -> explicit action bar -> result/diagnostic feedback

## Design principles
- One concern per surface: provider behavior belongs with the provider; runtime behavior belongs in system settings
- Make the active source explicit: show whether a model came from the upstream catalog, built-in fallback, or a custom entry
- Prefer reversible, local actions: fetching is read-only, saving is scoped, deletion is confirmed
- Tradeoffs: keep Streamlit and existing JSON data for compatibility, so controls use clear panels instead of introducing a new component system

## Visual language
- Color: existing TuLite navy `#1B2A4A`, orange accent `#FF7A45`, slate text, restrained teal/success feedback
- Typography: existing Streamlit sans-serif hierarchy; compact labels and readable helper copy
- Spacing/layout rhythm: grouped panels with consistent 12-16px spacing; action bars aligned with their panel
- Shape/radius/elevation: existing 10-16px radii, light borders, minimal shadows
- Motion: no decorative motion; use rerun/loading feedback only for network/model discovery actions
- Imagery/iconography: existing emoji labels are retained for compatibility; status/source badges should be concise

## Components
- Existing components to reuse: `settings-panel`, Streamlit expanders/tabs, `render_model_select_with_custom`, provider validation and secret storage helpers
- New/changed components: provider model discovery action, provider model catalog summary, role-aware model selectors, runtime settings panel
- Variants and states: not fetched, fetched, stale/failed, custom model, disabled provider, active provider
- Token/component ownership: keep styling in `apply_style()` and behavior in `app.py`

## Accessibility
- Target standard: usable keyboard-first Streamlit controls with visible labels and status text
- Keyboard/focus behavior: every action remains a native button/select/input; no click-only custom HTML controls
- Contrast/readability: keep existing dark text on light surfaces and avoid conveying source only by color
- Screen-reader semantics: use visible labels for model roles and action outcomes
- Reduced motion and sensory considerations: no new animation dependencies

## Responsive behavior
- Supported breakpoints/devices: desktop-first local browser with narrow viewport fallback
- Layout adaptations: provider cards stack fields and keep the fetch/save actions adjacent to their context; avoid relying on a permanently expanded sidebar
- Touch/hover differences: controls remain native and full-width where Streamlit collapses columns

## Interaction states
- Loading: fetching models shows a scoped spinner and preserves existing catalog
- Empty: explain that a provider can be added first, then models fetched from its endpoint
- Error: show sanitized upstream error while keeping prior model assignments
- Success: show count, source, and last-updated time after fetch/save/test
- Disabled: connection test disabled only when no usable key exists; delete disabled for active tasks
- Offline/slow network: fetch uses bounded HTTP timeout and actionable retry feedback

## Content voice
- Tone: direct, neutral, operational Chinese
- Terminology: use “提供商”, “上游模型目录”, “标题模型”, “视觉模型”, “出图模型”, “运行设置” consistently
- Microcopy rules: explain source and scope before destructive or network actions; do not duplicate a control in another page

## Implementation constraints
- Framework/styling system: Streamlit single-file app with existing JSON persistence
- Design-token constraints: extend existing CSS classes; no new dependency or frontend rewrite
- Performance constraints: model discovery is explicit and bounded; do not fetch on every rerun
- Compatibility constraints: preserve existing provider fields and fallback model behavior for old data
- Test/screenshot expectations: targeted unit tests for catalog parsing/role selection plus local browser smoke check

## Open questions
- [ ] Whether each provider should eventually support per-role capability overrides beyond upstream metadata / heuristic classification
