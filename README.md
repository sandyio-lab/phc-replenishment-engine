# Autonomous PHC Medicine Replenishment & Supply Chain Resilience Engine

An AI-powered platform that automates medicine stock tracking, reordering, and inter-facility redistribution for Primary Health Centres (PHCs) across rural India — built for **Build with AI: Code for Communities**, Track 03: *Smart Health & Supply Chain Resilience*.

> Built for India — designed to scale from a single district to healthcare networks across states.

---

## Table of Contents

- [Problem Statement](#problem-statement)
- [Solution Overview](#solution-overview)
- [Key Features](#key-features)
- [System Architecture](#system-architecture)
- [Google AI Integration](#google-ai-integration)
- [Tech Stack](#tech-stack)
- [Team](#team)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Risk Mitigations](#risk-mitigations)
- [Hackathon Submission](#hackathon-submission)

---

## Problem Statement

Public healthcare across rural India faces severe medicine supply chain vulnerabilities:

- **High data-entry friction** — overburdened PHC staff rely on manual paper registers, causing delayed stock updates.
- **Reactive replenishment** — reorders are placed only after stock hits zero, ignoring vendor delivery lead times.
- **Communication gaps** — local vendors and district warehouses operate in regional languages and lack integration with rigid central dashboards.

The result: frequent stock-outs of essential medicines (Paracetamol, ORS, antibiotics) and wastage from expired drugs.

## Solution Overview

Instead of acting as a passive inventory dashboard, this platform automates the end-to-end replenishment lifecycle:

- **Zero-touch ingestion** — captures stock via invoice/package scanning using Gemini Vision.
- **Predictive reordering** — automatically detects low stock and upcoming expiries based on daily consumption velocity.
- **Surge-aware demand** — Gemini assesses seasonal and field-reported disease signals (e.g. monsoon illness, a local flu outbreak) and raises expected consumption before stock runs low.
- **Automated vernacular dispatch** — generates and sends reorder requests to local vendors in their native language via SMS/WhatsApp.
- **End-to-end tracking & inter-PHC transfers** — tracks shipments in real time and auto-routes emergency transfers from nearby surplus PHCs when vendor delivery is delayed, ranked by real road distance and drive time.

## Key Features

| Feature | Description |
|---|---|
| Invoice/Package Scanning | Staff photograph a delivery register or carton; Gemini Vision extracts drug name, batch number, quantity, and expiry date into structured JSON. |
| Vernacular Voice Logging | Staff log daily distribution via voice notes in regional languages (Hindi, Kannada, Tamil, etc.). |
| Dynamic Reorder Engine | Reorders trigger based on consumption velocity and supplier lead times, not static zero-stock thresholds. |
| Demand Surge Assessment | Gemini reasons over district, month, and field-reported signals to return a bounded surge multiplier (1.0–2.5x) with affected drug categories, rationale, and confidence. The multiplier is applied to daily consumption before the reorder point is calculated. |
| Expiry Watchlist | Daily scan flags batches expiring within 30–60 days for priority distribution or transfer. |
| Inter-PHC Redistribution | Identifies neighboring PHCs (within ~20 km) with surplus stock and generates peer-to-peer transfer requests. |
| Road-Aware Transfer Routing | Donor PHCs are ranked by real road distance and drive time (OpenStreetMap OSRM, with optional Google Maps Routes API), and each suggestion shows its route source. |
| Multilingual Vendor Requisition | Formats verified orders into localized text/voice messages dispatched via SMS/WhatsApp. |
| Live Pipeline Tracking | Order lifecycle tracked through: `Requisition Sent → Vendor Confirmed → In Transit → Delivered & Verified`. |
| Offline-First PWA | Stock logging works with zero connectivity; actions queue locally and sync automatically once online. |
| Network Map | Interactive map of PHC locations, color-coded by stock health (green = healthy, red = at risk). |

## System Architecture

```
[ PHC Staff ] ---> (Gemini Vision OCR / Voice) ---> [ Offline-First PWA ]
                                                             │
                                                     (Background Sync)
                                                             ▼
[ District Supplier ] <--- (WhatsApp / SMS API) <--- [ Python / Node Backend ]
         │                                                   │
  (Status Updates)                               (Demand Engine & Relays)
         ▼                                                   ▼
[ Live Track Dashboard ] <------------------------- [ PostgreSQL Database ]
```

**Layer 1 — Data Capture & Ingestion (Frontend + Gemini Vision)**
Offline-first PWA for stock logging; Gemini Vision OCR parses invoices/cartons into structured JSON; vernacular voice logging for distribution updates.

**Layer 2 — Intelligence & Demand Engine (Backend Core)**
Dynamic reorder calculation based on consumption velocity and lead times; Gemini-based surge multiplier applied to expected consumption; expiry watchlist; inter-PHC redistribution logic for emergency transfers, with donors ranked by road distance and drive time.

**Layer 3 — Action & Delivery Tracking (Communications & Workflow)**
Gemini-formatted multilingual vendor requisitions dispatched via SMS/WhatsApp; live four-stage pipeline tracking.

## Google AI Integration

| Touchpoint | Google AI Tool | Core Function |
|---|---|---|
| Document Scanning | Gemini Vision API | Extracts batch details, dosage, and expiry dates from invoices and packaging photos. |
| Vernacular Communications | Gemini Flash API | Translates structured order payloads into localized, polite procurement text/voice notes for district suppliers. |
| Voice Command Parsing | Gemini Multimodal | Converts rural dialect audio logs into deterministic JSON database updates. |
| Demand Surge Risk Assessment | Gemini Flash API (structured JSON) | Reasons over district, month, and field-reported signals (e.g. "flu cases rising in Velhe block") to output a validated demand-surge multiplier (1.0–2.5x) with affected drug categories, rationale, and confidence. The multiplier feeds the reorder engine so orders are placed *before* a seasonal or outbreak-driven stock-out. |

Gemini is deliberately scoped to **translation, parsing, extraction, and bounded risk assessment only** — all quantities, drug IDs, and reorder math are computed deterministically in backend code (see [Risk Mitigations](#risk-mitigations)). The surge multiplier is schema-validated, capped at 1.0–2.5x, and falls back to a static Indian seasonality table if Gemini is unavailable.

**Roadmap:** once 3+ months of real consumption history is available in BigQuery, the surge layer is replaced by a trained Vertex AI AutoML Forecasting model (nightly batch predictions) with IMD weather data and state health-bulletin signals as covariates.

**Road routing:** transfer suggestions use OpenStreetMap OSRM by default, and the Google Maps Routes API when a `GOOGLE_MAPS_API_KEY` is configured. If both are unavailable, the system falls back to a straight-line estimate.

## Tech Stack

- **Backend:** Python (Flask/FastAPI), PostgreSQL/SQLite
- **Frontend:** React / Next.js PWA with IndexedDB offline caching, Leaflet.js for mapping
- **AI/ML:** Google `google-genai` SDK — Gemini Vision, Gemini Flash, Gemini Multimodal
- **Routing:** OpenStreetMap OSRM (default), Google Maps Routes API (optional), haversine fallback
- **Messaging:** Twilio / Fast2SMS / Meta WhatsApp API
- **Deployment:** Cloud Run / Cloud Functions (suggested)

## Team

| Role | Owner | Responsibilities |
|---|---|---|
| Backend Dev 1 — System Architecture & Core Logic | Shreyas | Database models (PHCs, Inventory, Vendors, Orders), reorder math, inter-PHC distance calculations, data seeding script (50+ synthetic Indian PHCs, NLEM medicine codes), REST API gateway. |
| Backend Dev 2 — Google GenAI & Communications | Sandra | Gemini Vision invoice parsing, Gemini audio intent/quantity extraction, multilingual SMS engine (Gemini Flash + Fast2SMS), Gemini demand-surge multiplier, road-routing module (OSRM / Google Maps). |
| Frontend Dev 1 — PHC Mobile App / PWA | Bhavana | Worker-facing mobile web app, camera/audio capture UI, local inventory tables with expiry alerts. |
| Frontend Dev 2 — District Admin & Network Dashboard | Darren | Kanban-style supply pipeline, interactive Leaflet.js PHC map, inter-PHC transfer modal UI with distance, ETA, and route-source badge. |

## Project Structure

```
.
├── backend/
│   ├── models/            # PHC, Inventory, Vendor, Order schemas
│   ├── services/          # reorder math, distance calc, demand engine
│   ├── genai/              # Gemini Vision / Audio / SMS / surge multiplier handlers, road routing
│   ├── api/                # Flask/FastAPI routes
│   └── scripts/            # synthetic data seeding
├── frontend/
│   ├── worker-app/         # PHC staff PWA (camera, voice, inventory view)
│   └── admin-dashboard/    # district admin pipeline + map
└── README.md
```
*(Update to match the actual repository layout before submission.)*

## Getting Started

```bash
# Backend
cd backend
pip install -r requirements.txt
python scripts/seed_data.py      # populate synthetic PHC + medicine data
uvicorn api.main:app --reload    # or `flask run`

# Frontend
cd frontend/worker-app
npm install
npm run dev
```

Set the following environment variables before running:

```
GEMINI_API_KEY=           # Gemini API key
DATABASE_URL=             # PostgreSQL/SQLite connection string
FAST2SMS_API_KEY=         # Fast2SMS API key for dispatching regional SMS alerts to PHC vendors
GOOGLE_MAPS_API_KEY=      # Optional — enables Google Maps Routes API; without it, OSRM is used
OSRM_BASE_URL=            # Optional — defaults to the public OSRM demo server
```

## Risk Mitigations

| Risk | Mitigation |
|---|---|
| LLM hallucination in drug names/quantities | Deterministic guardrails — raw calculations and drug IDs are managed strictly by backend code; Gemini is restricted to text translation, invoice parsing, and a bounded surge multiplier, all with strict JSON schema validation. |
| Vendor digital exclusion | Human-in-the-loop approval — every reorder requires a single confirmation tap from the PHC pharmacist before sending. |
| Intermittent rural connectivity | Store-and-forward architecture — actions queue in IndexedDB while offline and sync automatically once connectivity is restored. |
| Surge model unavailable or wrong | Multiplier is capped at 1.0–2.5x and schema-validated; on any Gemini failure the system falls back to a static seasonality table, and every result is tagged with its source. |
| Routing service unavailable | Provider chain — Google Maps (if configured), then OSRM, then a straight-line estimate — so transfer suggestions never fail; each result shows which source produced it. |

## Hackathon Submission

Built for **Build with AI: Code for Communities — Second Edition** (Google Cloud), Track 03: *Smart Health & Supply Chain Resilience*.

Submission package checklist:
- [ ] Source code (public or access-granted GitHub repo)
- [ ] Demo video (3–5 min, end-to-end walkthrough)
- [ ] Pitch deck (10–12 slides)
- [ ] Brief description (2–3 lines)
- [ ] Deployed live link

---
*Solving for India — built to scale from a single district to healthcare networks across states.*
