# Meridian

Multi-tenant commercial analytics platform for B2B SaaS companies. Turns product usage and CRM data into revenue forecasts, churn/health scores, feature adoption insights, sales funnel diagnostics, and automated executive reporting.

## What it does

| Capability                         | Description                                                     |
| ---------------------------------- | --------------------------------------------------------------- |
| **Revenue / cashflow forecasting** | Usage-driven revenue forecasts with confidence intervals        |
| **Feature adoption & engagement**  | Cohort analysis of feature usage by firm type, role, and tenure |
| **Churn & health scoring**         | Composite health score + ML-based churn risk classification     |
| **CRM data quality & enrichment**  | Automated audit and enrichment of CRM records                   |
| **Sales funnel analysis**          | Stage-duration tracking, stall detection, conversion prediction |
| **Executive reporting**            | Automated digest replacing manual spreadsheet reporting         |

## Stack

- **Database:** PostgreSQL
- **Transform layer:** dbt
- **Product usage data:** Amplitude
- **CRM data:** HubSpot
- **Forecasting:** Prophet
- **Churn/health ML:** scikit-learn, XGBoost
- **Analytics:** Python, pandas
- **Visualization:** Plotly
- **API:** FastAPI
- **Frontend / tenant portal:** Next.js
- **BI/dashboards:** Metabase
- **CI/CD:** GitHub Actions

## Status

Early development. Every table, query, and ML model run is scoped by tenant (`tenant_id`) — Meridian is built multi-tenant from the ground up, not retrofitted later. Currently bootstrapped on a synthetic data generator that mimics multi-tenant Amplitude/HubSpot data shapes, so the rest of the stack (dbt, ML, API, BI) can be built and validated before live tenant integrations (HubSpot OAuth, direct SDK ingestion) are wired up.

## Getting Started

```bash
docker compose up -d
```

More setup instructions will land here as the stack comes online.

## License

MIT — see [LICENSE](LICENSE).
