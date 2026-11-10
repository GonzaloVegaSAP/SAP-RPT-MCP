# rpt-mcp

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![License: Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-green.svg)](LICENSE)
[![MCP compatible](https://img.shields.io/badge/MCP-compatible-purple.svg)](https://modelcontextprotocol.io/)
[![SAP RPT](https://img.shields.io/badge/SAP-RPT%20Playground-0070f3.svg)](https://rpt.cloud.sap/)

An [MCP (Model Context Protocol)](https://modelcontextprotocol.io/) server that connects AI assistants — Claude, Joule, Cursor, Windsurf, and any MCP-compatible client — to the [SAP RPT Playground](https://rpt.cloud.sap/) prediction API.

Once installed, you talk to your AI assistant in plain language and it calls the right RPT tool automatically:

> *"I have 90 days of daily sales. Forecast the next 14 days with an 80% confidence interval."*

> *"Classify these support tickets by urgency and department using my labeled examples."*

No Python knowledge required after setup.

---

## What this server provides

| Endpoint | Capability |
|---|---|
| `/api/predict` | Few-shot tabular prediction — classify or fill in missing values using example rows |
| `/api/forecast` | Zero-shot time-series forecasting with confidence intervals and covariates |
| `/api/systemone` | Structured decisions — answer typed questions (yes/no, category, score) about any content |

---

## Installation

### Prerequisites

- Python 3.11 or later — check with `python3 --version`
- An SAP RPT API token — you will create one in step 3 below

### Step 1 — Clone and install

Click the **Code** button on the repository page, copy the HTTPS URL, then run:

```bash
git clone <repo-url>
cd rpt-mcp
pip install -r requirements.txt
```

### Step 2 — Add the server to your AI client

Choose the client you use and follow the instructions for it.

#### Claude Code

Add this block inside the `"mcpServers"` key of `~/.claude/settings.json`:

```json
"sap-rpt-playground": {
  "type": "stdio",
  "command": "python3",
  "args": ["/absolute/path/to/rpt-mcp/server.py"]
}
```

Replace `/absolute/path/to/rpt-mcp` with the actual path where you cloned the repo.  
On macOS you can get it by running `pwd` from inside the cloned folder.

After saving the file, restart Claude Code (or run `/mcp` to reload servers).

#### Cursor

Add to `.cursor/mcp.json` in your home directory (create the file if it does not exist):

```json
{
  "mcpServers": {
    "sap-rpt-playground": {
      "command": "python3",
      "args": ["/absolute/path/to/rpt-mcp/server.py"]
    }
  }
}
```

Restart Cursor after saving.

#### Windsurf

Add to `~/.codeium/windsurf/mcp_config.json`:

```json
{
  "mcpServers": {
    "sap-rpt-playground": {
      "command": "python3",
      "args": ["/absolute/path/to/rpt-mcp/server.py"]
    }
  }
}
```

#### HTTP mode (Joule Work Desktop, web clients)

```bash
python3 server.py --http
# Server is now listening on http://localhost:8020/mcp
```

To use a different port:

```bash
MCP_PORT=9000 python3 server.py --http
```

### Step 3 — Get an SAP RPT API token

1. Go to [https://rpt.cloud.sap/](https://rpt.cloud.sap/) and sign in with your SAP account.
2. Open **Settings → API Tokens → Create new token**.
3. Give it a name (e.g. `my-mcp`) and copy the generated token.

### Step 4 — Configure your token

With the server now registered in your AI client, ask your assistant:

```
Call setup_auth with my RPT token: <paste-your-token-here>
```

The assistant calls `setup_auth(token="…")`, which saves the token to a local `.env` file inside the project folder. You only need to do this once — the token persists across restarts.

Alternatively, configure it manually without using the assistant:

```bash
cd rpt-mcp
cp .env.example .env
# Open .env in any editor and set:  RPT_API_TOKEN=<your-token>
```

> Your token is stored only in the local `.env` file (which is git-ignored) and is sent exclusively to `https://rpt.cloud.sap` over HTTPS. It never leaves your machine.

### Step 5 — Verify the connection

Ask your assistant:

```
Call test_connection to check that RPT is working.
```

Expected output:

```
Connected to https://rpt.cloud.sap
HTTP 200 — OK ✓
```

If you see `HTTP 401`, your token is invalid or expired — repeat step 3.  
If you see a connection error, check your network or VPN.

---

## Your first prediction

Once setup is complete, try this in your AI assistant:

```
I want to predict the sales group for a new product.

Context data (products I already know):
[
  {"PRODUCT": "Laptop Pro",      "CATEGORY": "Electronics", "SALESGROUP": "Enterprise"},
  {"PRODUCT": "Standing Desk",   "CATEGORY": "Furniture",   "SALESGROUP": "Office"},
  {"PRODUCT": "USB Hub",         "CATEGORY": "Electronics", "SALESGROUP": "Enterprise"},
  {"PRODUCT": "Office Chair",    "CATEGORY": "Furniture",   "SALESGROUP": "Office"}
]

Query (product to classify):
[{"PRODUCT": "Wireless Headset", "CATEGORY": "Electronics"}]

Target column: SALESGROUP
```

The assistant calls `predict()` and `parse_predict_response()` for you. You will see something like:

```json
{
  "num_predictions": 1,
  "predictions": [
    {
      "SALESGROUP": {
        "prediction": "Enterprise",
        "confidence": 0.87
      }
    }
  ]
}
```

---

## Tools reference

### Auth

| Tool | Description |
|---|---|
| `setup_auth(token)` | Save your API token to `.env` and verify the connection. Run once at setup. |
| `test_connection()` | Check that the configured token is valid and the service is reachable. |

---

### Predict (`/api/predict`)

SAP RPT Predict is a **few-shot in-context learner** for tabular data. You provide context rows (with known target values) and query rows (without targets) — the model fills in the predictions without any training or fine-tuning step.

**Works for:** classification, regression, and multi-target prediction (up to 10 columns at once).

| Tool | Description |
|---|---|
| `build_predict_payload(…)` | Build and inspect the request body without sending it |
| `predict(…)` | Run a prediction and return the raw API response |
| `parse_predict_response(raw)` | Extract predictions and confidence scores into a readable summary |

**Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `context_data` | JSON array or CSV | Training rows with real target values. Min 2, max 100,000. |
| `query_data` | JSON array or CSV | Rows to predict. Max 512 per call. |
| `target_columns` | string | Comma-separated column(s) to predict, e.g. `"churn"` or `"category,price"` |
| `context_mode` | `"default"` \| `"deep"` | `"deep"` is more accurate but slower |
| `index_column` | string (optional) | Column used as row identifier in the response |
| `top_feature_scores` | int 1–20 (0 = off) | Include feature importance per prediction |
| `top_relevant_rows` | int 1–20 (0 = off) | Include the most similar context rows per prediction |
| `data_source_url` | HTTPS URL (optional) | Remote CSV instead of inline rows (e.g. a pre-signed S3 URL). When set, `context_data`, `query_data`, and `target_columns` are ignored. |

**Example prompt:**
```
I have customer records with a "churn" column (1 = churned, 0 = stayed).
Use the first 80 rows as context and predict churn for the last 20.
Show results with confidence scores.
```

---

### Forecast (`/api/forecast`)

SAP RPT Forecast is a **zero-shot time-series model**. It requires only historical values — no labels, no training pipeline. It detects trends, seasonality, and cyclical patterns automatically.

| Tool | Description |
|---|---|
| `build_forecast_payload(…)` | Build and inspect the request body without sending it |
| `forecast(…)` | Run a forecast and return the raw API response |
| `parse_forecast_response(raw)` | Extract step-by-step forecasts and confidence intervals |
| `raw_forecast(payload)` | Send a fully custom JSON payload (multiple series, multivariate, hierarchical) |

**Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `series_data` | JSON array or CSV | Historical values. Accepts flat `[1,2,3]`, dicts `[{"value":1}]`, or CSV. Recommend ≥ 10 points. |
| `horizon` | int 1–90 | Number of future steps to forecast |
| `target_column` | string | Column name if `series_data` is dicts or CSV (default: `"value"`) |
| `confidence_interval` | float 0–1 | Width of the confidence band (default 0.8 = 80%) |
| `timestamps` | JSON array (optional) | ISO-8601 timestamps matching the series length |
| `past_covariates` | JSON object (optional) | External variables known in the past, e.g. `{"temperature":[...]}` |
| `future_covariates` | JSON object (optional) | Variables known in the forecast window (length must equal `horizon`) |
| `clip_min` / `clip_max` | float (optional) | Bound the output, e.g. `clip_min=0` for non-negative quantities |
| `enhanced_forecast` | bool | Enable enhanced mode for potentially better accuracy |
| `cross_learning` | bool | Enable cross-learning across series (useful when forecasting several related series together) |

**Example prompt:**
```
Here are 90 days of daily sales: [12, 14, 11, 15, 18, 13, ...].
Forecast the next 14 days with an 80% confidence interval.
Values cannot go below 0.
```

---

### Decisions (`/api/systemone`)

SAP RPT SystemOne answers **structured typed questions** about any content, learning from a small set of labeled examples. No training pipeline — provide 2–2,048 examples and the model generalises immediately.

| Tool | Description |
|---|---|
| `build_decisions_payload(…)` | Build and inspect the request body without sending it |
| `decisions(…)` | Run decisions and return the raw API response |
| `parse_decisions_response(raw)` | Extract answers, confidence scores, and probability distributions |

**Question types:**

| Type | Answer format | What the model returns |
|---|---|---|
| `"noul"` | `true` / `false` | Probability of `true` (0.0–1.0) |
| `"choice"` | Option key (string) | Winning option + full probability distribution |
| `"score"` | Level index as string (`"0"`, `"1"`, …) | Expected score + per-level probabilities |

> **Important:** For `"score"` questions, every declared level must appear in at least one example. If level `"0"` is declared but no example uses it, the API returns a 400 error.

**Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `state` | string | The content to evaluate — free text, a JSON object, or an array |
| `questions` | JSON object | Question definitions keyed by name. Max 10 per call. |
| `examples` | JSON array | Labeled examples `[{"state": …, "answers": {…}}]`. Min 2, max 2,048. |
| `model` | string | Model to use (default: `"sap-rpt-1.6"`) |

**Example questions JSON:**
```json
{
  "urgent":   { "type": "noul",   "instructions": "Is this message urgent?" },
  "dept":     { "type": "choice", "instructions": "Which department handles this?",
                "criteria": { "billing": "Invoice issues", "delivery": "Shipping", "product": "Product defects" } },
  "priority": { "type": "score",  "instructions": "Priority level.",
                "criteria": ["Low", "Medium", "High", "Critical"] }
}
```

**Example prompt:**
```
I have 50 labeled customer support tickets with category, urgency, and priority score.
Classify this new ticket: "My order never arrived and I need it for a presentation tomorrow."
```

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `No API token configured` | Token not set | Run `setup_auth` or create `.env` manually (step 4) |
| `HTTP 401` | Token invalid or expired | Generate a new token at https://rpt.cloud.sap/ |
| `HTTP 429` | Rate limit hit | Wait for the `Retry-After` seconds shown in the response |
| `HTTP 400 — labels not demonstrated` | A score level has no example | Add at least one example for every declared score level |
| `HTTP 504 ERR_FORECAST_FAILED` from forecast | The `/api/forecast` backend service is currently unavailable — the Playground API gateway returns "The time-series service returned an error" regardless of payload. `predict` and `decisions` are unaffected. The `forecast` tool code and payload format are correct; contact SAP support or check [rpt.cloud.sap](https://rpt.cloud.sap/) for service status. |
| Server not found in MCP client | Path wrong in config | Use the absolute path from `pwd` in the cloned folder |
| `command not found: python3` | Python not in PATH | Use the full path, e.g. `/usr/bin/python3` or `/usr/local/bin/python3` |

---

## Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `RPT_API_TOKEN` | Yes | — | Your SAP RPT API token |
| `RPT_BASE_URL` | No | `https://rpt.cloud.sap` | Override the API base URL |
| `RPT_CONTEXT_MODE` | No | `default` | Default context mode for predict calls (`"default"` or `"deep"`) |
| `MCP_PORT` | No | `8020` | Port for HTTP transport (`--http` mode) |

---

## API limits

| Limit | Value |
|---|---|
| Query rows per predict call | 512 |
| Context rows per predict call | 100,000 |
| Target columns per predict call | 10 |
| Forecast horizon | 1–90 steps |
| Questions per decisions call | 10 |
| Examples per decisions call | 2,048 |
| Rate limit response | HTTP 429 with `Retry-After` header |

---

## Project structure

```
rpt-mcp/
├── server.py          # MCP server — all 12 tools defined here
├── .env               # Your API token (git-ignored, created by setup_auth)
├── .env.example       # Template — copy to .env and fill in your token
├── requirements.txt   # Python dependencies
├── CHANGELOG.md       # Version history
├── CONTRIBUTING.md    # Contribution guidelines
└── README.md          # This file
```

---

## Security

- The `.env` file is listed in `.gitignore` and will never be committed.
- Tokens are sent only to `https://rpt.cloud.sap` via HTTPS.
- No credentials are logged, printed, or stored anywhere other than `.env`.
- The server makes no outbound connections other than to `RPT_BASE_URL`.

---

## Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## License

This project is licensed under the [Apache License 2.0](LICENSE).

It is not an official SAP product. SAP RPT is a service of SAP SE — see [rpt.cloud.sap](https://rpt.cloud.sap/) for terms of use.
