# PHC Engine — Autonomous Medicine Replenishment & Supply Chain Resilience for Primary Health Centres

An AI-powered platform that automates medicine stock tracking, reordering, and inter-facility redistribution for Primary Health Centres (PHCs) across rural India. Built for **Build with AI: Code for Communities — Second Edition**, Track 03: *Smart Health & Supply Chain Resilience*.

> Built for India — designed to scale from a single district to healthcare networks across states. The demo network covers three Karnataka districts; the data model is state-agnostic.

**Code:** [github.com/sandyio-lab/phc-replenishment-engine](https://github.com/sandyio-lab/phc-replenishment-engine)

---

## Table of Contents

- [Problem Statement](#problem-statement)
- [Solution Overview](#solution-overview)
- [Who It Serves](#who-it-serves)
- [Live Demo](#live-demo)
- [Key Features](#key-features)
- [System Architecture](#system-architecture)
- [Google AI Integration](#google-ai-integration)
- [Built for India, Ready to Scale](#built-for-india-ready-to-scale)
- [Backend & Data](#backend--data)
- [Tech Stack](#tech-stack)
- [Team](#team)
- [Project Structure](#project-structure)
- [Risk Mitigations](#risk-mitigations)
- [Known Limitations](#known-limitations)
- [Future Prospects](#future-prospects)
- [Hackathon Submission](#hackathon-submission)

---

## Problem Statement

Over 65% of India lives in rural areas, where PHCs are the first point of care. India has about 31,882 PHCs, yet only around 30% operate with all the required infrastructure, and roughly 8% of sub-centres and PHCs sit in hard-to-reach areas. *(Figures as cited in our pitch deck, from The Spine Foundation and PMF IAS.)*

Medicine supply chains at these centres are fragile:

- **High data-entry friction** — overburdened PHC staff rely on manual paper registers, causing delayed stock updates.
- **Reactive replenishment** — reorders are placed only after stock hits zero, ignoring vendor delivery lead times.
- **Communication gaps** — local vendors and district warehouses operate in regional languages and lack integration with rigid central dashboards.

The result: frequent stock-outs of essential medicines (Paracetamol, ORS, antibiotics) and wastage from expired drugs.

## Solution Overview

Instead of acting as a passive inventory dashboard, PHC Engine automates the replenishment lifecycle in four layers — **Capture, Intelligence, Action, Tracking**:

- **Zero-touch ingestion** — captures stock from a photo of an invoice or carton (Gemini Vision) or a spoken voice note (Gemini audio).
- **Predictive reordering** — flags low stock and upcoming expiries using daily consumption velocity and supplier lead times, not a static "zero stock" trigger.
- **Season-aware demand** — Gemini estimates the expected seasonal demand surge for a district and month (for example monsoon gastro-intestinal illness) and raises the reorder point *before* stock runs low.
- **Vernacular vendor dispatch** — composes reorder requests in the vendor's own language and sends them by SMS.
- **Order tracking & inter-PHC transfers** — moves orders through a validated lifecycle and finds nearby PHCs with surplus stock when a PHC is running low.

## Who It Serves

| Who | What they get |
|---|---|
| **PHC staff** | Scan, confirm, done. Less paperwork and fewer stock-outs. |
| **District coordinators** | One dashboard for stock, alerts, order status and inter-PHC transfers. |
| **Patients** | Medicines available when they reach the centre. |

## Live Demo

The prototype is deployed on Vercel, so there is nothing to install: open the live app, or watch the demo video. <!-- CONFIRM: paste the live Vercel URL here as a link. -->

A quick tour:

1. **Worker app** — pick a PHC, photograph an invoice or record a voice note, review the pre-filled entry and save. The inventory list updates with stock status and expiry flags.
2. **District dashboard** — see the PHC network map colour-coded by stock health, then open a low-stock PHC and view suggested inter-PHC transfers with road distance and drive time. **Dispatch Stock** creates the transfer order.
3. **Order pipeline** — follow orders from Requisition Sent to Verified. Marking an order Delivered from the worker app updates stock at the receiving PHC (and the donor PHC for transfers).

<details>
<summary>Want to run it yourself?</summary>

```bash
pip install -r requirements.txt
cd backend
python seed.py --reset               # load synthetic data
uvicorn app.main:app --reload        # API + interactive docs at http://localhost:8000/docs
```

Create a `.env` file:

```
GEMINI_API_KEY=           # Required for Vision, Audio, SMS and Surge (GOOGLE_API_KEY also accepted)
DATABASE_URL=             # Optional — SQLite by default; use PostgreSQL for hosted deployments
FAST2SMS_API_KEY=         # Optional — SMS stays in dry-run without it
GOOGLE_MAPS_API_KEY=      # Optional — without it, OSRM is used
OSRM_BASE_URL=            # Optional — defaults to the public OSRM demo server
```

Never commit real API keys. Without a Gemini key the app still runs: surge falls back to the seasonal table and SMS to a plain-English template, while invoice and voice extraction ask staff to enter data manually.

<!-- CONFIRM: add how the two frontends in frontend/Worker and frontend/Dashboard are served locally, and test on a clean clone. -->

</details>

## Key Features

### Capture

| Feature | What it does | Powered by |
|---|---|---|
| **Invoice & package scanning** | A photo of an invoice, delivery register or carton becomes structured stock data: drug, batch, quantity, unit and expiry, each line with a confidence score. Staff review the pre-filled form before saving. | Gemini Vision |
| **Vernacular voice logging** | A voice note ("received two hundred ORS packets") becomes a transcript, the detected language and a signed stock movement (`+` received, `−` dispensed or disposed). Unclear speech returns `unclear` with a zero change, never a guess. | Gemini multimodal audio |
| **PHC worker app** | Mobile-first web app for stock in and out, expiry and low-stock flags, bed occupancy and daily attendance. Interface labels in English, Hindi, Kannada and Tamil. | HTML/JS, Tailwind |

### Intelligence

| Feature | What it does | Powered by |
|---|---|---|
| **Dynamic reorder engine** | Reorder point = surge-adjusted daily consumption × (supplier lead time + safety stock days), recomputed whenever stock changes. | Deterministic backend code |
| **Season-aware demand surge** | A bounded 1.0–2.5x multiplier for a district and month, with rationale and confidence. Falls back to a built-in Indian seasonal table if the API fails. | Gemini Flash, seasonal table fallback |
| **Stock status & expiry watchlist** | Every batch is Expired, Expiring (within 30 days), Critical (3 days of stock or less), Low or Healthy. The watchlist lists batches expiring within a 1–180 day window, soonest first. | Deterministic backend code |
| **Inter-PHC redistribution** | For a PHC with Low or Critical items, finds PHCs within the radius (default 20 km) holding more than twice their own reorder point, and suggests a transfer capped at the donor's surplus and the recipient's need. | Deterministic backend code |
| **Road-aware routing** | Ranks donor PHCs by real road distance and drive time, with a visible source label on each estimate. Never fails: Google Maps, then OSRM, then a straight-line estimate. | OSRM, Google Maps Routes API |

### Action

| Feature | What it does | Powered by |
|---|---|---|
| **Auto-generated reorders** | A demand scan turns at-risk items into **Draft** orders sized to a 30-day supply, assigned to the fastest active vendor in the district. Items with an open order are skipped. | Deterministic backend code |
| **Multilingual vendor SMS** | Composes a polite reorder in the vendor's language and script, with an English back-translation for verification, and sends it by SMS. Dry-run by default. Available through the API; triggering it from the screens is the next step. | Gemini Flash, Fast2SMS |

### Tracking

| Feature | What it does | Powered by |
|---|---|---|
| **Order lifecycle** | `Draft → Requisition Sent → Vendor Confirmed → In Transit → Delivered → Verified` (or `Cancelled`), with strict transition validation. Delivery automatically adjusts stock at the receiving PHC and, for transfers, the donor PHC. | FastAPI, SQLAlchemy |
| **District dashboard** | PHC network map coloured by stock health (green healthy, amber low, red at risk) with bed occupancy, a Kanban board of orders, and a transfer view with a **Dispatch Stock** button. | Live API, SVG map |
| **Beds & staff attendance** | Ward-level bed occupancy (General 10, Maternity 4, Emergency 2 per PHC) and daily staff check-in and check-out in IST, shown on the network map. | FastAPI, SQLAlchemy |

## System Architecture

```
[ PHC Staff ] ──(photo / voice)──> [ PHC Worker App ]
                                          │
                                          ▼
                    ┌──────────── FastAPI Backend (/api/v1) ────────────┐
                    │                                                   │
                    │  AI Integrations        Core Logic                │
                    │  ├─ Gemini Vision OCR   ├─ Demand engine          │
                    │  ├─ Gemini Audio        │   (+ surge multiplier)  │
                    │  ├─ Gemini SMS Engine   ├─ Order state machine    │
                    │  └─ Gemini Surge        ├─ Inter-PHC radius search│
                    │                         └─ Road routing module    │
                    └───────────────┬───────────────────────────────────┘
                                    │
                        SQLite / PostgreSQL (SQLAlchemy)
        phcs · vendors · inventory_items · orders · beds · staff_members · attendance_records
                                    │
              ┌─────────────────────┴─────────────────────┐
              ▼                                           ▼
   [ District Control Console ]                 [ Fast2SMS ] ──> [ Local Vendor ]
   map · pipeline · transfers                    (regional-language reorder SMS)
```

**Layer 1 — Capture:** the worker app sends invoice photos and voice notes to the AI endpoints, which return validated JSON. The AI layer only extracts; staff review the pre-filled form, and the save is a separate backend call.

**Layer 2 — Intelligence:** reorder points are recomputed on every inventory change using velocity, lead time, safety stock and the surge multiplier. Expiry scans and inter-PHC radius queries run on the same data.

**Layer 3 — Action:** low-stock alerts become localized vendor SMS messages, and at-risk items become Draft orders.

**Layer 4 — Tracking:** orders move through a validated state machine, and the district dashboard shows live status and transfers.

## Google AI Integration

| Touchpoint | Google AI Tool | Core Function |
|---|---|---|
| Document Scanning | Gemini Vision (`google-genai`) | Extracts batch, dosage, quantity and expiry from invoice and carton photos into `InvoiceExtraction` / `MedicineLineItem` schemas. |
| Voice Command Parsing | Gemini multimodal audio | Transcribes and detects language, then outputs `StockMovement` records with signed quantity deltas, action type and confidence. |
| Vernacular Communications | Gemini Flash | Turns a structured low-stock payload into a natural reorder message in the vendor's language, with an English back-translation. |
| Demand Surge Assessment | Gemini Flash (structured JSON) | Reasons over district and month to output a validated 1.0–2.5x surge multiplier with rationale and confidence. |

**Design principle:** Gemini is scoped to *extraction, translation and bounded risk assessment only.* All quantities, drug IDs and reorder math are computed by deterministic backend code, and every Gemini output is validated against a Pydantic schema.

**Resilience of the AI layer:** every module retries with exponential backoff. Beyond that:

- **Vision** tries a chain of Gemini models in turn.
- **SMS** falls back to a plain-English template if message composition fails.
- **Surge** falls back to a deterministic seasonal table, and each result is tagged with its source (`gemini` or `seasonal_fallback`).
- **Vision and audio** return an error through the API when extraction fails, and the worker app then asks staff to fill in the form manually.

**Surge is a v1 hybrid, not a trained model:** an LLM assessment bounded by a rule-based table. The planned next step is a Vertex AI Forecast model trained on BigQuery history (see [Future Prospects](#future-prospects)).

## Built for India, Ready to Scale

- **State-agnostic data model:** PHCs carry state, district, block and language; vendors carry district and preferred language. Onboarding a new region means loading master data, not changing code.
- **Multilingual by design:** the worker UI supports English, Hindi, Kannada and Tamil; voice notes and vendor messages are handled by Gemini in any Indian language it supports.
- **NLEM-coded inventory:** medicines use National List of Essential Medicines codes, so records line up across states.
- **Provider-agnostic routing:** routing takes only latitude and longitude, so it has no India-specific logic. OSRM is the default, Google Routes API is used when configured, and it degrades to a haversine distance with an ETA estimate.
- **Runs on any phone or browser:** no new hardware, and vendors receive plain SMS with no app or login.
- **Demo scope:** the seeded network is 19 PHCs across Chikkaballapur, Tumkur and Mysuru (Karnataka), with Kannada as the local language.

### Beyond India (BRICS)

The design separates what travels from what is local. This is a design-level plan, **not implemented in code**.

| Country-agnostic modules (take coordinates and region as inputs) | India-specific layers (swapped per country) |
|---|---|
| Routing and ETA (provider-agnostic, haversine fallback) | Essential-medicines list (NLEM) |
| Surge reasoning | Language |
| Stock and reorder engine | SMS provider (Fast2SMS) |
| | Seasonality table and seed data |

India is the built market; Brazil, South Africa, China and Russia are the target extensions. Google Maps availability varies by country (for example China and Russia), so those regions would use a local routing provider or the haversine fallback.

## Backend & Data

The backend is a FastAPI service with one router per domain (PHCs, inventory, orders, vendors, analytics, beds, attendance and AI). Interactive API documentation is generated automatically at `/docs`, which also makes it straightforward for a ministry or state system to integrate with.

The three AI endpoints are the heart of the API:

| Endpoint | Purpose |
|---|---|
| `POST /ai/invoice` | Invoice or carton photo → validated stock line items |
| `POST /ai/audio` | Voice note → transcript and validated stock movements |
| `POST /ai/reorder-message` | Low-stock alert → localized vendor SMS (dry-run unless `send` is set) |

**Database (7 tables):** `phcs`, `vendors`, `inventory_items` (batch-level, NLEM-coded, with expiry and consumption metrics), `orders` (procurement and transfer orders with audit timestamps), `beds`, `staff_members` and `attendance_records`.

**Synthetic data (`seed.py`):** 19 PHCs across 3 Karnataka districts (Chikkaballapur 9, Mysuru 5, Tumkur 5), 8 district vendors, 31 NLEM essential medicines (589 inventory rows), 304 beds, 36 staff members, and 220 orders and inter-PHC transfers spread across the pipeline stages. Inventory is deliberately seeded with a realistic mix of healthy, low, critical, expiring and expired stock so the alerts, map and transfer suggestions have something to show.

## Tech Stack

- **Backend:** Python, FastAPI, SQLAlchemy, SQLite (dev) / PostgreSQL
- **AI:** Google `google-genai` SDK (Gemini API) — Gemini Vision, Flash and multimodal audio, with Pydantic schema validation
- **Frontend:** HTML/JS with Tailwind (worker app) and custom CSS (district console); SVG network map
- **Routing:** OpenStreetMap OSRM (default), Google Maps Routes API (optional), haversine fallback
- **Messaging:** Fast2SMS (Quick route)
- **Deployment:** Vercel

## Team

| Role | Owner | Responsibilities |
|---|---|---|
| Backend Dev 1 — System Architecture & Core Logic | Shreyas Nair | Database models (PHCs, Inventory, Vendors, Orders, Beds, Staff), reorder math and demand engine, inter-PHC distance calculations, seeding script, REST API gateway. |
| Backend Dev 2 — Google GenAI & Communications | Sandra Jose | Gemini Vision invoice parsing, Gemini audio stock updates, multilingual SMS engine (Gemini Flash + Fast2SMS), Gemini demand-surge multiplier, road-routing module. |
| Frontend Dev 1 — PHC Mobile App | Bhavana M | Worker-facing mobile web app, camera and voice capture UI, local inventory tables with expiry alerts, multilingual UI. |
| Frontend Dev 2 — District Admin & Network Dashboard | Darren Rufus Antony | Order pipeline board, PHC network map, inter-PHC transfer view. |

## Project Structure

```
phc-replenishment-engine/
├── backend/
│   ├── ai_integration/
│   │   ├── gemini_vision_ocr.py         # Invoice/package photo → structured JSON
│   │   ├── gemini_audio_stock_update.py # Voice note → stock movement JSON
│   │   ├── gemini_sms_engine.py         # Vernacular vendor requisition + SMS dispatch
│   │   ├── gemini_surge_multiplier.py   # Demand-surge risk assessment
│   │   ├── maps_routing.py              # Road distance/ETA (OSRM / Google Maps / fallback)
│   │   └── run_test.py                  # Manual test runner for the SMS module
│   ├── app/
│   │   ├── core/                        # Database setup, demand engine (reorder math, transfers)
│   │   ├── models/                      # PHC, Inventory, Vendor, Order, Bed, Staff models
│   │   ├── schemas/                     # Pydantic request/response schemas
│   │   ├── routes/                      # ai, analytics, attendance, beds, inventory, orders, phcs, vendors
│   │   └── main.py                      # FastAPI entry point
│   └── seed.py                          # Synthetic PHC, vendor, medicine, bed, staff and order data
├── frontend/
│   ├── Worker/                          # PHC staff app (camera, voice, inventory view)
│   └── Dashboard/                       # District console: map, pipeline, transfers
├── context/                             # Hackathon guidelines, prototype and team notes
├── docs/
├── requirements.txt
├── vercel.json                          # Vercel deployment config
└── README.md
```

## Risk Mitigations

| Risk | Mitigation |
|---|---|
| LLM hallucination in drug names or quantities | Deterministic guardrails — quantities, drug IDs and reorder math are computed in backend code. Gemini output is validated against strict Pydantic schemas with per-line confidence, and unclear audio returns `unclear` with a zero delta instead of a guess. Extracted values only pre-fill a form that staff review before saving. |
| Accidental or wrong vendor messages | SMS dispatch is dry-run by default, and every message ships with an English back-translation so non-speakers can verify it before sending. Auto-generated orders start as Draft, not sent. |
| Vendor digital exclusion | Reorders go out by SMS rather than an app or dashboard login, in the vendor's own language. |
| Invalid order changes | The order state machine rejects illegal transitions, and stock only adjusts on confirmed delivery. |
| Gemini unavailable or rate-limited | Retries with backoff, a model fallback chain for Vision, a plain-English template for SMS, a static seasonal table for surge, and manual entry in the worker app for scan and voice. |
| Surge estimate wrong | Multiplier is capped at 1.0–2.5x, schema-validated, and tagged with its source. |
| Routing service unavailable | Provider chain — Google Maps (if configured), then OSRM, then a straight-line estimate — so transfer suggestions never fail. |

## Known Limitations

- **Connectivity:** the worker app needs an internet connection; it shows an online/offline badge but does not yet queue entries offline.
- **Demo data scope:** seed data covers one state (Karnataka), three districts and one language (Kannada), with 19 PHCs.
- **Surge input:** the surge module can reason over a free-text field report (e.g. "flu cases rising in Velhe block"), but the reorder engine currently passes only district and month, and always uses the general drug category.
- **Transfer trigger:** transfers are suggested when a PHC's stock is Low or Critical; they are not yet triggered by a vendor delivery delay.
- **Dashboard actions:** the dashboard's pipeline board is read-only. Order status is advanced from the worker app, and transfers are dispatched from the dashboard.
- **Approval step:** auto-generated reorders start as Draft, but there is no one-tap pharmacist confirmation screen yet.
- **Voice logging:** only the first detected medicine is used to pre-fill the form, and the direction (received or given) is chosen in the UI. Tested mainly in English; regional-language accuracy is not yet validated.
- **SMS:** live delivery is not yet exercised end to end (verified in dry-run), SMS is not yet triggered from the screens, and delivery of native-script text on basic handsets is not yet validated. Vendor replies are not yet parsed, and vendors do not yet receive status updates by SMS.
- **Manual inventory entries:** items added by hand use a placeholder code and default consumption values, so their reorder points are only indicative.
- **Security:** the API has no authentication yet.
- **Map:** the network map is a schematic SVG, not real map tiles.
- **Routing:** the public OSRM demo server has no uptime guarantee.
- **Hosting:** SQLite on Vercel is not persistent; use PostgreSQL for a lasting deployment.

## Future Prospects

These are planned directions, not shipped features.

### Near term (post-hackathon)

- **Live SMS dispatch:** connect the SMS engine to the order flow, run Fast2SMS in live mode, then add delivery receipts and vendor reply parsing to confirm orders and send status updates by SMS.
- **Offline-first PWA:** service worker and IndexedDB store-and-forward so PHCs with no signal can keep logging and sync later.
- **One-tap pharmacist approval:** a confirmation screen before every auto-generated reorder is sent.
- **Field-signal surge input:** let health workers submit local reports (e.g. a rising flu cluster) and feed them into the surge assessment per drug category.
- **Vendor-delay trigger:** start emergency transfers automatically when a vendor's expected delivery date is missed.
- **Wire the dashboard end to end:** persisted pipeline updates from the dashboard, plus real map tiles (Leaflet).
- **Regional-language validation:** test and tune voice logging in Hindi, Kannada, Tamil and Marathi with real PHC staff.

### Scale-out

- **Vertex AI forecasting:** once 3+ months of real consumption data sits in BigQuery, replace the Gemini surge multiplier with a trained Vertex AI Forecast model, using data.gov.in and IMD weather inputs as covariates.
- **Multi-state onboarding:** load PHC and vendor master data per state and enable each state's languages. The data model already carries state, district, block and language.
- **Government system integration:** connect with e-Aushadhi and district warehouse systems, and add barcode/QR scanning for faster stock entry.
- **Low-connectivity fallbacks:** SMS/USSD reporting for PHCs without smartphones.
- **WhatsApp channel:** an optional Business API channel for vendors who prefer it, alongside SMS.
- **Authentication and roles:** separate access for PHC staff, district administrators and vendors.

### Long-term vision

- **Optimised redistribution:** treat surplus-to-deficit transfers as an assignment problem weighted by distance, transport cost and shelf life (e.g. OR-Tools).
- **Outbreak early warning:** anomaly detection on footfall and consumption, with explainable recommendations so health officials can see *why* a transfer is suggested.
- **Staffing vs. load:** correlate the attendance and bed-occupancy data already collected with patient load to flag under-staffed PHCs.
- **Cross-border cooperation (BRICS):** swap the India-specific layers per country (see [Beyond India](#beyond-india-brics)), then move to federated forecasting, where each region trains on its own data and shares only model updates (with differential privacy), so data-poor regions benefit from data-rich ones without raw health data crossing borders.

## Hackathon Submission

Built for **Build with AI: Code for Communities — Second Edition** (Google Cloud), Track 03: *Smart Health & Supply Chain Resilience*.

Submission package checklist:
- [ ] Source code — [github.com/sandyio-lab/phc-replenishment-engine](https://github.com/sandyio-lab/phc-replenishment-engine)
- [ ] Demo video (3–5 min, end-to-end walkthrough)
- [ ] Pitch deck (10–12 slides)
- [ ] Brief description (2–3 lines)
- [ ] Deployed live link

---
*Solving for India — built to scale from a single district to healthcare networks across states.*
