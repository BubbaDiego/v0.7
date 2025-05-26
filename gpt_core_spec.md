# 📘 GPT Input Specification — Modular Portfolio Analysis
**Version:** 1.0  
**Generated:** 2025-05-26 20:08:36  
**Author:** Geno

---

## 🎯 Purpose
This specification defines the modular JSON format for sending portfolio, alert, and analysis context to GPT. It allows structured evaluation of risk, hedging, and performance.

---

## 🧩 Top-Level File: `gpt_response_wrapper.json`
Acts as the main bundle reference.
```json
{
  "type": "gpt_analysis_bundle",
  "version": "1.0",
  "generated": "YYYY-MM-DDTHH:MM:SSZ",
  "meta_file": "gpt_meta_input.json",
  "definitions_file": "gpt_definitions_input.json",
  "alert_limits_file": "gpt_alert_limits_input.json",
  "module_reference_file": "gpt_module_references.json",
  "current_snapshot_file": "snapshot_<DATE>.json",
  "previous_snapshot_file": "snapshot_<DATE>.json",
  "instructions_for_ai": "Prompt for GPT's use"
}
```

---

## 📁 Referenced Files

### 🧠 `gpt_meta_input.json`
```json
{
  "type": "meta",
  "version": "1.0",
  "owner": "Geno",
  "strategy": "hedged, automated trading",
  "goal": "optimize exposure while minimizing risk",
  "notes": "Background context"
}
```

### 🧾 `gpt_definitions_input.json`
```json
{
  "type": "definitions",
  "metrics": {
    "travel_percent": "Defines change from entry to current price",
    "heat_index": "Composite risk metric"
  }
}
```

### 🚨 `gpt_alert_limits_input.json`
```json
{
  "alert_ranges": {
    "heat_index_ranges": {
      "enabled": true,
      "low": 7.0,
      "medium": 33.0,
      "high": 66.0
    }
  }
}
```

### 🧠 `gpt_module_references.json`
```json
{
  "modules": {
    "PositionCore": {
      "role": "Manages enrichment, snapshots, sync"
    },
    "HedgeCalcServices": {
      "role": "Suggests hedge rebalancing"
    }
  }
}
```

### 📦 `snapshot_<DATE>.json`
Includes:
- `totals`: aggregate metrics
- `positions`: list of full position objects

```json
{
  "positions": [
    {
      "id": "...",
      "asset_type": "BTC",
      "position_type": "LONG",
      "leverage": 5.0,
      "travel_percent": -12.4
    }
  ]
}
```

---

## 🧠 GPT Behavior

GPT will:
- Analyze differences between snapshots
- Compare metrics to thresholds
- Identify alert violations
- Recommend improvements (rebalance, de-risk)

---

## ✅ Required Files Summary

| File                        | Required | Description                        |
|-----------------------------|----------|------------------------------------|
| gpt_response_wrapper.json   | ✅       | Master bundle and routing          |
| gpt_meta_input.json         | ✅       | Strategy and owner intent          |
| gpt_definitions_input.json  | ✅       | Metric definitions                 |
| gpt_alert_limits_input.json | ✅       | Alert configuration thresholds     |
| gpt_module_references.json  | ✅       | Module behaviors and descriptions  |
| snapshot_<date>.json        | ✅       | Portfolio states (prev + current)  |

