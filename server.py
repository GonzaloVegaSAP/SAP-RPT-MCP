#!/usr/bin/env python3
"""MCP server for the SAP RPT Playground API.

Provides tools for:
  • /api/predict   — tabular in-context prediction (classification & regression)
  • /api/forecast  — time-series forecasting with covariates and confidence intervals
  • /api/systemone — structured decisions (yes/no, multi-class, ordinal scoring)

Authentication
--------------
Get your API token at https://rpt.cloud.sap/ (Settings → API Tokens) and either:
  1. Run setup_auth(token="<your-token>") once — saves to .env automatically.
  2. Copy .env.example to .env and fill in RPT_API_TOKEN.

Transports
----------
  python3 server.py          # stdio (Claude Code, Cursor, Windsurf …)
  python3 server.py --http   # HTTP on http://localhost:8020/mcp (Joule, etc.)
"""

import csv
import io
import json
import os
import sys
from pathlib import Path
from typing import Any, Optional

import httpx
from dotenv import load_dotenv, set_key
from fastmcp import FastMCP

# ── Configuration ─────────────────────────────────────────────────────────────

_ENV_PATH = Path(__file__).parent / ".env"
load_dotenv(_ENV_PATH)

BASE_URL      = os.environ.get("RPT_BASE_URL", "https://rpt.cloud.sap").rstrip("/")
CONTEXT_MODE  = os.environ.get("RPT_CONTEXT_MODE", "default")
PREDICT_LIMIT = 512    # max query rows per request
FORECAST_MAX  = 90     # max forecast horizon

mcp = FastMCP("sap-rpt-playground")

# ── Internal helpers ───────────────────────────────────────────────────────────

def _token() -> str:
    """Return the configured API token, or empty string if not set."""
    return os.environ.get("RPT_API_TOKEN", "")


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {_token()}",
        "Content-Type": "application/json",
    }


def _check_auth() -> Optional[str]:
    if not _token():
        return (
            "No API token configured. "
            "Call setup_auth(token='<your-token>') to set it, "
            "or copy .env.example → .env and fill RPT_API_TOKEN. "
            "Get a token at https://rpt.cloud.sap/ (Settings → API Tokens)."
        )
    return None


def _post(path: str, body: Any) -> httpx.Response:
    return httpx.post(
        f"{BASE_URL}{path}",
        headers=_headers(),
        json=body,
        timeout=120.0,
    )


def _fmt(resp: httpx.Response) -> str:
    try:
        body = json.dumps(resp.json(), indent=2, ensure_ascii=False)
    except Exception:
        body = resp.text
    return f"HTTP {resp.status_code}\n{body}"


def _parse_rows(data: str) -> list[dict]:
    """Parse a JSON array or CSV string into a list of row dicts."""
    data = data.strip()
    try:
        parsed = json.loads(data)
        if isinstance(parsed, list):
            return parsed
        raise ValueError("Expected a JSON array.")
    except json.JSONDecodeError:
        reader = csv.DictReader(io.StringIO(data))
        rows = list(reader)
        if not rows:
            raise ValueError("CSV appears to be empty.")
        # Coerce numeric strings
        result = []
        for row in rows:
            clean = {}
            for k, v in row.items():
                try:
                    clean[k] = int(v)
                except (ValueError, TypeError):
                    try:
                        clean[k] = float(v)
                    except (ValueError, TypeError):
                        clean[k] = v
            result.append(clean)
        return result


def _parse_series(data: str, target_column: str = "value") -> list[float]:
    """Parse a numeric series from JSON array (flat or dicts) or CSV."""
    data = data.strip()
    try:
        parsed = json.loads(data)
        if isinstance(parsed, list):
            if parsed and isinstance(parsed[0], (int, float)):
                return [float(v) for v in parsed]
            if parsed and isinstance(parsed[0], dict):
                return [float(row[target_column]) for row in parsed]
    except json.JSONDecodeError:
        reader = csv.DictReader(io.StringIO(data))
        rows = list(reader)
        if rows and target_column in rows[0]:
            return [float(r[target_column]) for r in rows]
    raise ValueError(
        f"Cannot parse series. Accepted: flat JSON array [1,2,3], "
        f"JSON array of dicts with '{target_column}' key, "
        f"or CSV with '{target_column}' column."
    )


# ─────────────────────────────────────────────────────────────────────────────
# AUTH & CONFIG
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def setup_auth(token: str) -> str:
    """Configure your SAP RPT Playground API token.

    Run this tool once before using any other tool. The token is saved to the
    local .env file — it never leaves your machine.

    How to get a token:
      1. Go to https://rpt.cloud.sap/
      2. Sign in with your SAP account.
      3. Open Settings → API Tokens → Create new token.
      4. Copy the token and pass it here.

    Args:
        token: Your RPT API token (starts with 'rpt_' or similar).
    """
    if not token or len(token) < 8:
        return "Error: token appears too short. Check that you copied it correctly."

    # Save to .env (create file if it doesn't exist)
    _ENV_PATH.touch(exist_ok=True)
    set_key(str(_ENV_PATH), "RPT_API_TOKEN", token)
    os.environ["RPT_API_TOKEN"] = token  # apply immediately without restart

    # Verify it works
    try:
        resp = _post("/api/predict", {
            "rows": [
                {"x": 1, "y": "a"},
                {"x": 2, "y": "[PREDICT]"},
            ]
        })
        if resp.status_code in (200, 400):  # 400 means auth passed, payload may be wrong
            return (
                f"Token saved to {_ENV_PATH}.\n"
                f"Connection verified (HTTP {resp.status_code}). Ready to use."
            )
        if resp.status_code == 401:
            return "Token saved but verification failed (HTTP 401 — invalid token). Check it at https://rpt.cloud.sap/."
        return f"Token saved. Server returned HTTP {resp.status_code} — may need to retry."
    except httpx.RequestError as e:
        return f"Token saved, but could not reach {BASE_URL}: {e}"


@mcp.tool()
def test_connection() -> str:
    """Verify that the API token is configured and the RPT service is reachable."""
    err = _check_auth()
    if err:
        return err
    try:
        resp = _post("/api/predict", {
            "rows": [
                {"feature": "sunny",  "sales": 100},
                {"feature": "rainy",  "sales": 60},
                {"feature": "sunny",  "sales": "[PREDICT]"},
            ]
        })
        return (
            f"Connected to {BASE_URL}\n"
            f"HTTP {resp.status_code} — "
            + ("OK ✓" if resp.status_code == 200 else f"response: {resp.text[:200]}")
        )
    except httpx.RequestError as e:
        return f"Connection error: {e}"


# ─────────────────────────────────────────────────────────────────────────────
# PREDICT  (/api/predict)
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def build_predict_payload(
    context_data: str = "",
    query_data: str = "",
    target_columns: str = "",
    context_mode: str = "default",
    top_feature_scores: int = 0,
    top_relevant_rows: int = 0,
    index_column: Optional[str] = None,
    data_source_url: Optional[str] = None,
) -> str:
    """Build the JSON payload for /api/predict without sending it.

    Use this to inspect the exact body that will be sent before calling predict().

    SAP RPT Predict is a few-shot tabular predictor:
      - Context rows have the real target value → the model learns from them.
      - Query rows have [PREDICT] in the target column → the model fills them in.

    Two input modes:
      1. Inline rows: provide context_data + query_data + target_columns.
      2. Remote CSV:  provide data_source_url pointing to a publicly accessible CSV.
         The server fetches and downsamples it automatically; no inline rows needed.

    Args:
        context_data: Training/context rows as JSON array or CSV string.
                      Must include the target column(s) with real values.
                      Example: '[{"age":25,"income":30000,"churn":0}, ...]'
        query_data:   Rows to predict. May omit the target column.
                      Example: '[{"age":30,"income":35000}, ...]'
        target_columns: Comma-separated column name(s) to predict.
                        Example: "churn" or "category,priority"
        context_mode: "default" (fast) or "deep" (more accurate, higher latency).
        top_feature_scores: 1–20. Include feature importance per query row (0 = off).
        top_relevant_rows:  1–20. Include most relevant context rows per query row (0 = off).
        index_column: Optional column to use as row identifier in the response.
        data_source_url: HTTPS URL of a publicly accessible CSV file. When set,
                         context_data and query_data are ignored. The server fetches
                         and processes the file directly (e.g. a pre-signed S3 URL).
    """
    payload: dict[str, Any] = {}

    if data_source_url:
        payload["dataSource"] = {"type": "url", "url": data_source_url}
        if index_column:
            payload["index_column"] = index_column
        meta = {"endpoint": f"{BASE_URL}/api/predict", "mode": "remote_url", "payload": payload}
        return json.dumps(meta, indent=2, ensure_ascii=False)

    try:
        ctx_rows  = _parse_rows(context_data)
        qry_rows  = _parse_rows(query_data)
        tgt_cols  = [c.strip() for c in target_columns.split(",") if c.strip()]
    except ValueError as e:
        return f"Error parsing input: {e}"

    if not ctx_rows:
        return "Error: context_data is empty (and data_source_url not set)."
    if not qry_rows:
        return "Error: query_data is empty."
    if not tgt_cols:
        return "Error: target_columns is empty."

    def _inject(row: dict) -> dict:
        out = dict(row)
        for col in tgt_cols:
            out[col] = "[PREDICT]"
        return out

    all_rows = ctx_rows + [_inject(row) for row in qry_rows]
    payload["rows"] = all_rows
    payload["context_mode"] = context_mode
    if index_column:
        payload["index_column"] = index_column
    if top_feature_scores > 0:
        payload.setdefault("explanations", {})["top_column_scores"] = min(top_feature_scores, 20)
    if top_relevant_rows > 0:
        payload.setdefault("explanations", {})["top_relevant_context_rows"] = min(top_relevant_rows, 20)

    return json.dumps({
        "endpoint": f"{BASE_URL}/api/predict",
        "context_rows": len(ctx_rows),
        "query_rows": len(qry_rows),
        "target_columns": tgt_cols,
        "payload": payload,
    }, indent=2, ensure_ascii=False)


@mcp.tool()
def predict(
    context_data: str = "",
    query_data: str = "",
    target_columns: str = "",
    context_mode: str = "default",
    top_feature_scores: int = 0,
    top_relevant_rows: int = 0,
    index_column: Optional[str] = None,
    data_source_url: Optional[str] = None,
) -> str:
    """Predict missing values in tabular data using SAP RPT Predict.

    SAP RPT is a few-shot in-context learner for tabular data. It reads your
    context rows (with known target values) and predicts the target for your
    query rows — no training or fine-tuning required.

    Works for:
      • Classification: predict a category (churn, risk level, product class …)
      • Regression: predict a number (price, sales volume, lead time …)
      • Multi-target: predict several columns at once (up to 10)

    Two input modes:
      1. Inline rows: provide context_data + query_data + target_columns.
      2. Remote CSV:  provide data_source_url; the server fetches it directly.

    Args:
        context_data: Training/context rows as JSON array or CSV string.
                      Must include the target column(s) with real values.
                      Minimum 2 rows; up to 100,000.
                      Example: '[{"age":25,"income":30000,"churn":0}, ...]'
        query_data:   Rows to predict. May omit the target column.
                      1–512 rows per call.
                      Example: '[{"age":30,"income":35000}, ...]'
        target_columns: Comma-separated column name(s) to predict.
                        Example: "churn" or "category,priority"
        context_mode: "default" (balanced) or "deep" (more accurate, slower).
        top_feature_scores: 1–20. Return feature importance per prediction (0 = off).
        top_relevant_rows:  1–20. Return most relevant context rows per prediction (0 = off).
        index_column: Optional column name to use as row identifier in the response.
        data_source_url: HTTPS URL of a publicly accessible CSV (e.g. pre-signed S3).
                         When set, context_data/query_data/target_columns are ignored.
    """
    err = _check_auth()
    if err:
        return err

    if data_source_url:
        payload: dict[str, Any] = {"dataSource": {"type": "url", "url": data_source_url}}
        if index_column:
            payload["index_column"] = index_column
        resp = _post("/api/predict", payload)
        return _fmt(resp)

    try:
        ctx_rows = _parse_rows(context_data)
        qry_rows = _parse_rows(query_data)
        tgt_cols = [c.strip() for c in target_columns.split(",") if c.strip()]
    except ValueError as e:
        return f"Error parsing input: {e}"

    if not ctx_rows:
        return "Error: context_data is empty (and data_source_url not set)."
    if not qry_rows:
        return "Error: query_data is empty."
    if not tgt_cols:
        return "Error: target_columns is empty."
    if len(qry_rows) > PREDICT_LIMIT:
        return f"Error: query_data has {len(qry_rows)} rows; maximum per call is {PREDICT_LIMIT}."

    def _inj(row: dict) -> dict:
        out = dict(row)
        for col in tgt_cols:
            out[col] = "[PREDICT]"
        return out

    all_rows = ctx_rows + [_inj(row) for row in qry_rows]
    payload = {"rows": all_rows, "context_mode": context_mode}
    if index_column:
        payload["index_column"] = index_column
    if top_feature_scores > 0:
        payload.setdefault("explanations", {})["top_column_scores"] = min(top_feature_scores, 20)
    if top_relevant_rows > 0:
        payload.setdefault("explanations", {})["top_relevant_context_rows"] = min(top_relevant_rows, 20)

    resp = _post("/api/predict", payload)
    return _fmt(resp)


@mcp.tool()
def parse_predict_response(raw_response: str) -> str:
    """Parse and summarize a response from predict().

    Extracts predictions with confidence scores from the raw JSON response
    and returns a clean, readable summary.

    Args:
        raw_response: The raw string returned by predict().
    """
    body = raw_response.split("\n", 1)[-1] if raw_response.startswith("HTTP") else raw_response
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return json.dumps({"error": "Cannot parse response.", "raw": raw_response[:500]})

    # Playground API wraps the result under "prediction"
    inner = data.get("prediction", data)
    preds = inner.get("predictions", [])
    meta  = inner.get("metadata", {})
    result = []
    for row in preds:
        row_out: dict[str, Any] = {}
        for col, candidates in row.items():
            if isinstance(candidates, list) and candidates:
                best = candidates[0]
                row_out[col] = {
                    "prediction": best.get("prediction"),
                    "confidence": round(float(best.get("confidence") or 0), 4) or None,
                    "confidence_interval": best.get("confidence_interval"),
                    "alternatives": [
                        {"value": c.get("prediction"), "confidence": round(float(c.get("confidence") or 0), 4)}
                        for c in candidates[1:]
                    ] if len(candidates) > 1 else [],
                }
        result.append(row_out)

    return json.dumps({
        "num_predictions": meta.get("num_predictions", len(result)),
        "num_context_rows": (meta.get("num_rows", 0) or 0) - (meta.get("num_query_rows", 0) or 0),
        "context_mode": meta.get("context_mode"),
        "predictions": result,
    }, indent=2, ensure_ascii=False)


# ─────────────────────────────────────────────────────────────────────────────
# FORECAST  (/api/forecast)
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def build_forecast_payload(
    series_data: str,
    horizon: int,
    target_column: str = "value",
    confidence_interval: float = 0.8,
    timestamps: Optional[str] = None,
    past_covariates: Optional[str] = None,
    future_covariates: Optional[str] = None,
    clip_min: Optional[float] = None,
    clip_max: Optional[float] = None,
    enhanced_forecast: bool = False,
    cross_learning: bool = False,
) -> str:
    """Build the JSON payload for /api/forecast without sending it.

    Use this to inspect and verify the request body before calling forecast().

    Args:
        series_data: Historical time-series values. Accepts:
                     - Flat JSON array:        '[10, 12, 11, 14, 15, ...]'
                     - JSON array of dicts:    '[{"value":10}, {"value":12}, ...]'
                     - CSV with target_column header
        horizon:     Number of future steps to forecast (1–90).
        target_column: Column name if series_data is dicts or CSV (default: "value").
        confidence_interval: Width of confidence interval (0–1, default 0.8 = 80%).
        timestamps:  Optional ISO timestamps matching series length.
                     JSON array: '["2026-01-01","2026-01-02",...]'
        past_covariates:   Optional JSON object mapping covariate names to historical
                           value arrays. Example: '{"temp":[22,24,21,...]}'
        future_covariates: Optional JSON object mapping covariate names to forecast-
                           window value arrays (length must equal horizon).
        clip_min:    Clip forecast values to this minimum.
        clip_max:    Clip forecast values to this maximum.
        enhanced_forecast: Use enhanced forecast mode (may improve accuracy).
        cross_learning: Enable cross-learning across series (useful for multiple series).
    """
    try:
        values = _parse_series(series_data, target_column)
    except ValueError as e:
        return f"Error: {e}"

    if horizon < 1 or horizon > FORECAST_MAX:
        return f"Error: horizon must be between 1 and {FORECAST_MAX}."

    series_obj: dict[str, Any] = {"target": values}

    if timestamps:
        try:
            ts = json.loads(timestamps)
            series_obj["timestamp"] = ts
        except json.JSONDecodeError as e:
            return f"Error parsing timestamps: {e}"

    if past_covariates:
        try:
            series_obj["past_covariates"] = json.loads(past_covariates)
        except json.JSONDecodeError as e:
            return f"Error parsing past_covariates: {e}"

    if future_covariates:
        try:
            series_obj["future_covariates"] = json.loads(future_covariates)
        except json.JSONDecodeError as e:
            return f"Error parsing future_covariates: {e}"

    options: dict[str, Any] = {"confidence_interval": confidence_interval}
    if clip_min is not None:
        options["clip_min"] = clip_min
    if clip_max is not None:
        options["clip_max"] = clip_max
    if enhanced_forecast:
        options["enhanced_forecast"] = True
    if cross_learning:
        options["cross_learning"] = True

    payload = {
        "horizon": horizon,
        "data": [series_obj],
        "options": options,
    }

    return json.dumps({
        "endpoint": f"{BASE_URL}/api/forecast",
        "series_length": len(values),
        "horizon": horizon,
        "confidence_interval": confidence_interval,
        "payload": payload,
    }, indent=2, ensure_ascii=False)


@mcp.tool()
def forecast(
    series_data: str,
    horizon: int,
    target_column: str = "value",
    confidence_interval: float = 0.8,
    timestamps: Optional[str] = None,
    past_covariates: Optional[str] = None,
    future_covariates: Optional[str] = None,
    clip_min: Optional[float] = None,
    clip_max: Optional[float] = None,
    enhanced_forecast: bool = False,
    cross_learning: bool = False,
) -> str:
    """Forecast future values of a time series using SAP RPT Forecast.

    SAP RPT Forecast is a zero-shot time-series model — it requires no training
    data beyond the historical series itself. It detects trends, seasonality,
    and cyclical patterns automatically.

    Accepts a single univariate series. For multivariate forecasting or multiple
    series in one call, use the raw_forecast() tool with a custom payload.

    Args:
        series_data: Historical values. Accepts:
                     - Flat JSON array:        '[10, 12, 11, 14, 15, ...]'
                     - JSON array of dicts:    '[{"value":10}, {"value":12}, ...]'
                     - CSV with target_column header
                     Minimum: ~10 points recommended; more = better accuracy.
        horizon:     Number of future steps to forecast (1–90).
        target_column: Column name if series_data is dicts or CSV (default: "value").
        confidence_interval: Width of confidence interval, 0–1 (default 0.8 = 80%).
        timestamps:  Optional ISO timestamps matching series length, as JSON array.
                     Example: '["2026-01-01","2026-01-02",...]'
        past_covariates:   Optional external variables known in the past.
                           JSON object: '{"temperature":[22,24,21,...]}'
        future_covariates: Optional variables known in the forecast window.
                           JSON object (length must equal horizon).
        clip_min:    Floor for forecast values (useful for non-negative quantities).
        clip_max:    Ceiling for forecast values.
        enhanced_forecast: Enable enhanced forecast mode.
        cross_learning: Enable cross-learning across series.
    """
    err = _check_auth()
    if err:
        return err

    try:
        values = _parse_series(series_data, target_column)
    except ValueError as e:
        return f"Error: {e}"

    if horizon < 1 or horizon > FORECAST_MAX:
        return f"Error: horizon must be between 1 and {FORECAST_MAX}."

    series_obj: dict[str, Any] = {"target": values}

    if timestamps:
        try:
            series_obj["timestamp"] = json.loads(timestamps)
        except json.JSONDecodeError as e:
            return f"Error parsing timestamps: {e}"

    if past_covariates:
        try:
            series_obj["past_covariates"] = json.loads(past_covariates)
        except json.JSONDecodeError as e:
            return f"Error parsing past_covariates: {e}"

    if future_covariates:
        try:
            series_obj["future_covariates"] = json.loads(future_covariates)
        except json.JSONDecodeError as e:
            return f"Error parsing future_covariates: {e}"

    options: dict[str, Any] = {"confidence_interval": confidence_interval}
    if clip_min is not None:
        options["clip_min"] = clip_min
    if clip_max is not None:
        options["clip_max"] = clip_max
    if enhanced_forecast:
        options["enhanced_forecast"] = True
    if cross_learning:
        options["cross_learning"] = True

    payload = {
        "horizon": horizon,
        "data": [series_obj],
        "options": options,
    }

    resp = _post("/api/forecast", payload)
    return _fmt(resp)


@mcp.tool()
def parse_forecast_response(raw_response: str) -> str:
    """Parse and summarize a response from forecast().

    Extracts the forecast values, confidence intervals, and detected interval
    from the raw JSON response and returns a clean, step-by-step summary.

    Args:
        raw_response: The raw string returned by forecast().
    """
    body = raw_response.split("\n", 1)[-1] if raw_response.startswith("HTTP") else raw_response
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return json.dumps({"error": "Cannot parse response.", "raw": raw_response[:500]})

    # Playground forecast wraps result under "forecast" key
    fc     = data.get("forecast", data)
    result = fc.get("result", [])
    ci     = fc.get("confidence_interval_output", [])
    ts     = fc.get("result_timestamp", [])
    det    = fc.get("detected_interval", [])
    usage  = data.get("usage", fc.get("usage", {}))

    steps_raw = result[0][0] if result and result[0] else []
    lowers    = ci[0][0][0] if ci and ci[0] and ci[0][0] and len(ci[0][0]) > 0 else []
    uppers    = ci[0][0][1] if ci and ci[0] and ci[0][0] and len(ci[0][0]) > 1 else []
    stamps    = ts[0][0] if ts and ts[0] else []
    interval  = det[0] if det else None

    steps = []
    for i, val in enumerate(steps_raw):
        step: dict[str, Any] = {
            "step": i + 1,
            "forecast": round(float(val), 4),
        }
        if i < len(lowers) and i < len(uppers):
            step["lower_bound"] = round(float(lowers[i]), 4)
            step["upper_bound"] = round(float(uppers[i]), 4)
        if i < len(stamps):
            step["timestamp"] = stamps[i]
        steps.append(step)

    return json.dumps({
        "horizon": len(steps),
        "detected_interval": interval,
        "input_points": usage.get("input_time_points"),
        "output_points": usage.get("output_time_points"),
        "steps": steps,
    }, indent=2, ensure_ascii=False)


@mcp.tool()
def raw_forecast(payload: str) -> str:
    """Send a custom payload to /api/forecast.

    Use this for advanced scenarios:
      • Multiple series in one call (data array with several objects)
      • Multivariate targets (target as array of arrays)
      • Hierarchical forecasting
      • Quantile output

    Args:
        payload: Complete request body as a JSON string.
                 See https://rpt.cloud.sap/docs/api/forecast for the full schema.
    """
    err = _check_auth()
    if err:
        return err
    try:
        body = json.loads(payload)
    except json.JSONDecodeError as e:
        return f"Error: payload is not valid JSON: {e}"
    resp = _post("/api/forecast", body)
    return _fmt(resp)


# ─────────────────────────────────────────────────────────────────────────────
# DECISIONS  (/api/systemone)
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def build_decisions_payload(
    state: str,
    questions: str,
    examples: str,
    model: str = "sap-rpt-1.6",
) -> str:
    """Build the JSON payload for /api/systemone (Decisions) without sending it.

    Use this to verify the structure before calling decisions().

    Question types:
      • "noul"   — Yes/No. Answer must be true or false.
      • "choice" — Multi-class. Answer is the option name (string).
      • "score"  — Ordinal scale. Answer is the level index as a string ("0", "1" …).

    Args:
        state: The content to evaluate. Can be text, a JSON object (as string),
               or an array. This is what the model reads to answer the questions.
               Example: "Customer complaint: delivery arrived damaged."
        questions: JSON object mapping question keys to question configs.
                   Each question has "type", "instructions", and optionally "criteria".
                   Example:
                   '{
                     "urgent": {
                       "type": "noul",
                       "instructions": "Is this complaint urgent?"
                     },
                     "category": {
                       "type": "choice",
                       "instructions": "What category does this complaint fall into?",
                       "criteria": {
                         "delivery": "Issues with shipping or delivery",
                         "product":  "Issues with the product itself",
                         "billing":  "Issues with invoices or payments"
                       }
                     },
                     "severity": {
                       "type": "score",
                       "instructions": "Rate the severity of this complaint.",
                       "criteria": ["Low", "Medium", "High", "Critical"]
                     }
                   }'
        examples: JSON array of labeled examples with "state" and "answers".
                  Minimum 2 examples.
                  Example:
                  '[
                    {"state": "Package arrived crushed.", "answers": {"urgent": true, "category": "delivery", "severity": "2"}},
                    {"state": "Wrong item was shipped.",   "answers": {"urgent": false, "category": "product",  "severity": "1"}}
                  ]'
        model: Model to use (default: "sap-rpt-1.6").
    """
    try:
        q_obj   = json.loads(questions)
        ex_list = json.loads(examples)
    except json.JSONDecodeError as e:
        return f"Error parsing questions or examples: {e}"

    payload: dict[str, Any] = {
        "state":     state,
        "questions": q_obj,
        "examples":  ex_list,
        "model":     model,
    }

    return json.dumps({
        "endpoint":      f"{BASE_URL}/api/systemone",
        "num_questions": len(q_obj),
        "num_examples":  len(ex_list),
        "model":         model,
        "payload":       payload,
    }, indent=2, ensure_ascii=False)


@mcp.tool()
def decisions(
    state: str,
    questions: str,
    examples: str,
    model: str = "sap-rpt-1.6",
) -> str:
    """Answer structured questions about any content using SAP RPT Decisions.

    SAP RPT SystemOne answers typed questions (yes/no, multi-class, ordinal)
    by learning from your labeled examples. No training pipeline needed — just
    provide 2–2,048 examples and it generalises immediately.

    Question types:
      • "noul"   — Yes/No. Returns probability of true (0.0–1.0).
      • "choice" — Multi-class. Returns winning option + full probability distribution.
      • "score"  — Ordinal scale. Returns expected score + per-level probabilities.

    Args:
        state: The content to evaluate. Text, a JSON object (serialised as string),
               or an array. This is what the model reads to answer the questions.
        questions: JSON object mapping question keys to question configs.
                   Each config has:
                     - "type"         (required): "noul", "choice", or "score"
                     - "instructions" (required): plain-language question
                     - "criteria"     (optional): labels/descriptions for choices or levels
                   Max 10 questions per call.
        examples: JSON array of {"state": ..., "answers": {...}} labeled examples.
                  Min 2, max 2,048. More examples = better accuracy.
        model: Model to use (default: "sap-rpt-1.6").

    Example questions JSON:
        '{
          "is_urgent": {"type":"noul",   "instructions":"Is this message urgent?"},
          "dept":      {"type":"choice", "instructions":"Which department handles this?",
                        "criteria":{"sales":"Sales inquiries","support":"Technical support","billing":"Billing issues"}},
          "priority":  {"type":"score",  "instructions":"Priority level.",
                        "criteria":["Low","Medium","High","Critical"]}
        }'

    Example examples JSON:
        '[
          {"state":"Server is down!",         "answers":{"is_urgent":true,  "dept":"support","priority":"3"}},
          {"state":"Can I get a discount?",   "answers":{"is_urgent":false, "dept":"sales",  "priority":"1"}},
          {"state":"Invoice number is wrong.","answers":{"is_urgent":false, "dept":"billing","priority":"1"}}
        ]'
    """
    err = _check_auth()
    if err:
        return err

    try:
        q_obj   = json.loads(questions)
        ex_list = json.loads(examples)
    except json.JSONDecodeError as e:
        return f"Error parsing questions or examples: {e}"

    if len(q_obj) > 10:
        return "Error: maximum 10 questions per call."
    if len(ex_list) < 2:
        return "Error: minimum 2 examples required."

    payload: dict[str, Any] = {
        "state":     state,
        "questions": q_obj,
        "examples":  ex_list,
        "model":     model,
    }

    resp = _post("/api/systemone", payload)
    return _fmt(resp)


@mcp.tool()
def parse_decisions_response(raw_response: str) -> str:
    """Parse and summarize a response from decisions().

    Returns a clean summary of each answer: type, result, confidence,
    and full probability distribution where available.

    Args:
        raw_response: The raw string returned by decisions().
    """
    body = raw_response.split("\n", 1)[-1] if raw_response.startswith("HTTP") else raw_response
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return json.dumps({"error": "Cannot parse response.", "raw": raw_response[:500]})

    # Playground decisions response: answers at root level
    answers = data.get("answers", {})
    usage   = data.get("usage", {})
    result: dict[str, Any] = {}

    for key, ans in answers.items():
        q_type = ans.get("type")
        entry: dict[str, Any] = {"type": q_type}

        if q_type == "noul":
            prob = ans.get("noul")
            entry["answer"]      = (prob >= 0.5) if prob is not None else None
            entry["probability_true"] = round(float(prob), 4) if prob is not None else None

        elif q_type == "choice":
            entry["answer"]      = ans.get("choice")
            entry["confidence"]  = round(float(ans.get("confidence", 0)), 4)
            entry["distribution"] = {
                k: round(float(v), 4)
                for k, v in (ans.get("probabilities") or {}).items()
            }

        elif q_type == "score":
            entry["answer"]           = ans.get("score")
            entry["expected_score"]   = round(float(ans.get("score", 0)), 4)
            legend                    = ans.get("legend", {})
            entry["label"]            = legend.get(str(round(ans.get("score", 0))), "")
            entry["distribution"]     = {
                legend.get(str(i), str(i)): round(float(v), 4)
                for i, v in enumerate(ans.get("probabilities") or [])
            }

        result[key] = entry

    return json.dumps({
        "questions_answered": len(result),
        "answers": result,
        "usage": usage,
    }, indent=2, ensure_ascii=False)


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if "--http" in sys.argv:
        port = int(os.environ.get("MCP_PORT", "8020"))
        print(f"Starting SAP RPT Playground MCP on http://localhost:{port}/mcp", flush=True)
        mcp.run(transport="http", host="127.0.0.1", port=port)
    else:
        mcp.run()
