# Meridian Runbook

Commercial-analytics SaaS platform. Ingests product usage (Amplitude) and CRM (HubSpot) data, then runs a real ELT + ML + BI stack on top: revenue forecasting, feature adoption analysis, churn/health scoring, CRM data quality, sales funnel analysis, and executive reporting. Currently bootstrapped on synthetic data (see `docs/guidelines/decisions.md` D00/D01) until live integrations are wired up.

## 1. Environment & Architecture
Meridian is multi-tenant: every table, query, and model run is scoped by `tenant_id` (see `docs/guidelines/decisions.md` D08). One tenant maps to one customer business.

- **PostgreSQL:** System of record. Raw events, CRM staging tables, dbt marts, ML outputs, and the encrypted `tenant_credentials` table (D09) — all `tenant_id`-scoped.
- **Generator service (`/data/generator`):** Python + pandas/numpy + Faker + SQLAlchemy. Bootstraps multi-tenant Amplitude/HubSpot-shaped data with engineered correlations (feature depth ↔ retention, usage ↔ revenue, adoption ↔ funnel velocity) until real tenants are connected (D01). Runs as its own Docker service, not a notebook.
- **dbt:** Transform layer. `staging/` → `intermediate/` → `marts/`, every model `tenant_id`-filtered.
- **Python ML containers:** Prophet (revenue forecasting), XGBoost (churn/health), pandas (adoption correlation, funnel stall detection) — trained per-tenant, never globally (D12).
- **FastAPI:** REST layer serving forecasts, health scores, adoption cohorts, funnel diagnostics, the weekly digest trigger, and the public telemetry ingestion endpoint (`/api/v1/telemetry/event`, D11).
- **HubSpot integration:** Custom OAuth app (not Nango/Merge.dev, D10) — Next.js-hosted "Connect HubSpot" flow, FastAPI token exchange, bidirectional sync service (inbound staging + audit, outbound allowlisted enrichment fields).
- **Amplitude integration:** Either tenant's existing Amplitude via Export API pull, or Meridian's own direct ingestion SDK (D11) — both land in the same `raw_events` shape.
- **Metabase:** Embedded BI for Executive/CS/Sales dashboards.
- **Next.js:** Tenant-facing settings portal (OAuth connect flows) plus leadership portal, embeds Metabase + Plotly.
- **GitHub Actions:** CI, scheduled generator increments, scheduled HubSpot/Amplitude sync workers, scheduled weekly digest.

## 2. Common Commands
- **Full stack (local):**
  ```bash
  docker compose up -d
  ```
- **Infra only:**
  ```bash
  docker compose up -d postgres
  ```
- **Run generator (seed or incremental):**
  ```bash
  python data/generator/main.py --mode seed
  python data/generator/update.py --days 3
  ```
- **dbt:**
  ```bash
  cd dbt && dbt run && dbt test
  ```
- **FastAPI (dev):**
  ```bash
  uvicorn src.meridian.main:app --host 0.0.0.0 --port 8000 --reload
  ```

## 3. Before Starting Multi-Step Work
Check `docs/guidelines/build-sequence.md` for what's next — it's dependency-ordered (no dates/phases) and tracks what's already done. Don't start something out of sequence without a specific reason; building ahead of a dependency tends to mean rework once that dependency actually lands. Check `docs/plans/` (dated, newest = most current) for an existing plan before starting new work. The six-workstream blueprint (see `docs/guidelines/decisions.md`) is the source of truth for scope — don't invent a seventh workstream without updating that doc first. Every feature is built end-to-end (backend, frontend, integration, tests, deployment, monitoring) per the Definition of Done in `decisions.md` — no layer-only PRs.

**Workflow for new/multi-step work (Claude Code):** use the `superpowers` skills explicitly — `brainstorming` and `writing-plans` before implementation, `subagent-driven-development` to execute an already-written plan with independent tasks. Don't rely on a vague "let's start building X" to implicitly trigger this chain — name the skills if there's any doubt. Plans/specs produced this way land in `docs/plans/` and `docs/specs/` (dated, newest = current), per the check above. On other assistants without this skill system, follow the same spirit — brainstorm/spec before implementing, plan before a multi-step build — using that tool's own equivalent capability.

## 4. Modular Guidelines Index
Detailed coding conventions, architectural decisions, and workflows are isolated to avoid context bloat:

- [docs/guidelines/domain-rules.md](docs/guidelines/domain-rules.md) — Coding conventions for the generator, dbt, ML/analytics, FastAPI, HubSpot/Amplitude integrations, and multi-tenancy & security.
- [docs/guidelines/decisions.md](docs/guidelines/decisions.md) — Locked architectural decisions: Definition of Done, the six-workstream mapping, the fixed stack, schema ownership, correlation-engineering requirements, API design, multi-tenancy, credentials storage, HubSpot/Amplitude integration strategy, per-tenant ML.
- [docs/guidelines/git-branching.md](docs/guidelines/git-branching.md) — Branching model, commit conventions, worktree usage, hook enforcement.
- [docs/guidelines/gotchas.md](docs/guidelines/gotchas.md) — Known traps and API route conventions (not exact paths — see `/docs` and `ai-best-practices.md` Rule 1).
- [docs/guidelines/testing.md](docs/guidelines/testing.md) — Testing strategy for generator determinism, dbt, ML models, API layer, multi-tenant integration testing, and e2e.
- [docs/guidelines/deployment.md](docs/guidelines/deployment.md) — Docker layout, environments, CI/CD pipelines, and monitoring/observability.
- [docs/guidelines/ai-best-practices.md](docs/guidelines/ai-best-practices.md) — Why the docs are structured this way, and the rules for keeping them from going stale.
- [docs/guidelines/build-sequence.md](docs/guidelines/build-sequence.md) — What to build next, dependency-ordered, no dates.

These rules apply regardless of which AI coding assistant is reading this file — they describe intended workflow and constraints, not tool-specific commands, except where a tool/skill is explicitly named (see `ai-best-practices.md` Rule 3) because leaving it unnamed would mean relying on inference instead of an instruction.
