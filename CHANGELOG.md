# Changelog

All notable changes to this project are documented here.

This project follows [Semantic Versioning](https://semver.org/).

---

## [1.0.0] — 2026-11-06

Initial public release.

### Added

- **`setup_auth(token)`** — save and verify an SAP RPT API token to `.env`
- **`test_connection()`** — verify token and service reachability

- **`build_predict_payload(…)`** — build and inspect a `/api/predict` request body
- **`predict(…)`** — run tabular few-shot prediction (classification & regression)
  - Supports inline rows (JSON array or CSV) and remote CSV via `data_source_url`
  - Optional `explanations`: feature importance and relevant context rows
  - Optional `index_column` for named row identifiers
- **`parse_predict_response(raw)`** — extract predictions and confidence scores

- **`build_forecast_payload(…)`** — build and inspect a `/api/forecast` request body
- **`forecast(…)`** — run zero-shot time-series forecasting
  - Supports timestamps, past covariates, and future covariates
  - Options: `confidence_interval`, `clip_min`, `clip_max`, `enhanced_forecast`, `cross_learning`
- **`parse_forecast_response(raw)`** — extract step-by-step forecasts and confidence intervals
- **`raw_forecast(payload)`** — send a fully custom forecast payload (multiple series, multivariate, hierarchical)

- **`build_decisions_payload(…)`** — build and inspect a `/api/systemone` request body
- **`decisions(…)`** — answer structured typed questions using few-shot examples
  - Supports `noul` (yes/no), `choice` (multi-class), and `score` (ordinal) question types
- **`parse_decisions_response(raw)`** — extract answers, confidence, and probability distributions

- stdio and HTTP/SSE transports via [fastmcp](https://github.com/jlowin/fastmcp)
- `.env`-based token storage with `setup_auth` auto-persist via `python-dotenv`
- `MCP_PORT` environment variable to override the HTTP port (default: 8020)
