# Autonomous PHC Medicine Replenishment & Supply Chain Resilience Engine

An AI-powered, offline-first platform that automates medicine stock tracking, dynamic reordering, and inter-facility redistribution for Primary Health Centres (PHCs) across rural India.

Built for **Build with AI: Code for Communities**, Track 03: *Smart Health & Supply Chain Resilience*.

> Built for India — designed to scale from a single district to healthcare networks across states.

---

## Table of Contents

- [Problem Statement](#problem-statement)
- [Solution Overview](#solution-overview)
- [Key Features](#key-features)
- [System Architecture](#system-architecture)
- [Google AI Integration](#google-ai-integration)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Risk Mitigations & Guardrails](#risk-mitigations--guardrails)
- [Team](#team)

---

## Problem Statement

Public healthcare networks across rural India face severe medicine supply chain vulnerabilities:

- **High Friction Data Entry:** Overburdened PHC staff rely on manual paper registers, causing delayed stock updates.
- **Reactive Replenishment:** Reorders are placed only after stock hits zero, ignoring vendor delivery lead times.
- **Communication Gaps:** Local vendors and district warehouses operate in regional languages and lack integration with rigid central dashboards.

**Impact:** Frequent stock-outs of essential medicines (Paracetamol, ORS, antibiotics) alongside simultaneous wastage from expired drugs.

---

## Solution Overview

Instead of acting as a passive inventory dashboard, this platform automates the end-to-end replenishment lifecycle:

- **Zero-Touch Ingestion:** Captures stock via invoice/package photo scanning using Gemini Vision.
- **Predictive Reordering:** Automatically detects low stock and upcoming expiries based on daily consumption velocity and vendor lead times.
- **Surge-Aware Forecasting:** Gemini assesses seasonal and field-reported disease signals (e.g., monsoon illness, local flu outbreaks) to apply a dynamic demand multiplier ($1.0\times$ to $2.5\times$) before stock runs low.
- **Automated Vernacular Dispatch:** Generates and sends reorder requisitions directly to local vendors in their native language via SMS/WhatsApp.
- **Smart Inter-PHC Transfers:** Identifies nearby surplus PHCs (within ~20 km) and automatically routes emergency transfers, ranked by real road distance and drive time.

---

## Key Features

| Feature | Description |
|---|---|
| **Invoice / Package Scanning** | Field staff photograph a delivery register or carton; Gemini Vision extracts drug name, batch number, quantity, and expiry date into structured JSON. |
| **Vernacular Voice Logging** | Staff log daily distribution via voice notes in regional languages (Hindi, Kannada, Tamil, etc.). |
| **Dynamic Reorder Engine** | Reorders trigger based on consumption velocity and supplier lead times rather than static zero-stock thresholds. |
| **Demand Surge Assessment** | Gemini reasons over district, month, and field-reported signals to return a bounded surge multiplier ($1.0\times$ to $2.5\times$) applied to daily consumption before calculating reorder points. |
| **Expiry Watchlist** | Daily automated scans flag batches expiring within 30–60 days for priority distribution or transfer. |
| **Inter-PHC Redistribution** | Identifies neighboring PHCs with surplus stock and generates peer-to-peer transfer requests. |
| **Road-Aware Transfer Routing** | Donor PHCs are ranked by real road distance and drive time (OpenStreetMap OSRM, with optional Google Maps Routes API). |
| **Multilingual Vendor Messaging** | Formats verified orders into localized text messages dispatched via Fast2SMS / WhatsApp API. |
| **Live Pipeline Tracking** | Order lifecycle tracked through four stages: `Requisition Sent → Vendor Confirmed → In Transit → Delivered & Verified`. |
| **Offline-First PWA** | Stock logging works with zero connectivity; actions queue locally in IndexedDB and sync automatically once online. |
| **Interactive Network Map** | Map interface displaying PHC locations color-coded by stock health (green = healthy, red = at risk). |

---

## System Architecture

```text
[ Field Staff ]
│
├──> Photo OCR (Gemini Vision) / Vernacular Voice Note (Gemini Multimodal)
│
▼
[ Offline-First PWA (Worker App) ] ──(IndexedDB Sync)──► [ Python Backend (FastAPI / Flask) ]
│
├──> Gemini AI Engine
├──> OSRM / Google Maps Routing
└──> PostgreSQL / SQLite DB
│
▼
[ District Supplier (WhatsApp / SMS) ]
│
▼
[ Live Track Admin Dashboard ]
---

```

## Google AI Integration

| Touchpoint | Google AI Tool | Core Function |
|---|---|---|
| **Document Scanning** | Gemini Vision API | Extracts batch details, dosage, and expiry dates from invoices and packaging photos. |
| **Voice Command Parsing** | Gemini Multimodal | Converts rural dialect audio logs into deterministic JSON database updates. |
| **Vernacular Communications** | Gemini Flash API | Translates structured order payloads into localized, polite procurement text for local suppliers. |
| **Demand Surge Assessment** | Gemini Flash API | Reasons over district, month, and field signals to output a validated demand-surge multiplier (1.0X to 2.5X) with rationale and confidence. |

> **AI Scoping Principle:** Gemini is strictly scoped to translation, parsing, extraction, and bounded risk assessment. All medicine quantities, drug IDs, and reorder math are calculated deterministically in backend Python code.

---

## Tech Stack

- **Frontend:** HTML5, JavaScript (Offline PWA with IndexedDB caching), Leaflet.js (Map Interface)
- **Backend:** Python (FastAPI / Flask), SQLAlchemy, PostgreSQL / SQLite (`phc.db`)
- **AI & ML:** Google Gemini SDK (`google-genai`) — Gemini Vision, Gemini Flash, Gemini Multimodal
- **Routing & Navigation:** OpenStreetMap OSRM API (Default), Google Maps Routes API (Optional fallback)
- **Messaging:** Fast2SMS / Meta WhatsApp API / Twilio
- **Deployment:** Cloud Run / Vercel

---

## Project Structure

```text
phc-replenishment-engine/
├── backend/
│   ├── ai_integration/
│   │   ├── gemini_vision_ocr.py          # Invoice/packaging photo → structured JSON
│   │   ├── gemini_audio_stock_update.py  # Voice note → stock movement JSON
│   │   ├── gemini_sms_engine.py          # Vernacular vendor requisition + SMS dispatch
│   │   ├── gemini_surge_multiplier.py    # Seasonal & outbreak demand-surge risk assessment
│   │   ├── maps_routing.py               # Road distance/ETA (OSRM / Google Maps / fallback)
│   │   └── run_test.py                   # Manual test runner for AI modules
│   ├── app/
│   │   ├── core/                         # DB setup, dynamic reorder math, demand engine
│   │   ├── models/                       # SQLAlchemy schemas (PHC, Inventory, Vendor, Orders)
│   │   ├── schemas/                      # Pydantic request/response schemas
│   │   ├── routes/                       # FastAPI routes (/api/v1)
│   │   └── main.py                       # Application entry point
│   ├── seed.py                           # Synthetic data seeder (50+ Indian PHCs, NLEM codes)
│   └── phc.db                            # SQLite database instance
├── frontend/
│   ├── worker/                           # PHC staff app (Camera, Audio, Offline PWA)
│   └── dashboard/                        # District admin pipeline, map, transfers
├── context/                              # Hackathon guidelines and project notes
├── api/
│   └── index.py                          # Serverless entry point
├── requirements.txt
├── vercel.json                           # Vercel deployment configuration
└── README.md
---

```

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js or a local static HTTP file server

### Environment Variables

Create a `.env` file in the root directory (or export variables in your environment):

```env
GEMINI_API_KEY=your_gemini_api_key
DATABASE_URL=sqlite:///./backend/phc.db
FAST2SMS_API_KEY=your_fast2sms_api_key       # Optional
GOOGLE_MAPS_API_KEY=your_google_maps_key     # Optional (OSRM used if omitted)
OSRM_BASE_URL=http://router.project-osrm.org  # Optional demo server

### Setup Instructions

1. Clone the repository:

```bash
git clone <repository-url>
cd phc-replenishment-engine
```

2. Install Backend Dependencies:

```bash
pip install -r backend/requirements.txt
```

3. Seed the Database:

```bash
python backend/seed.py
```

4. Run the Backend API Server:

```bash
uvicorn backend.app.main:app --reload
```

5. Run Frontend Applications:

Serve frontend/worker/index.html for field staff and frontend/dashboard/index.html for district management using any static file server.


Risk Mitigations & Guardrails:

### LLM Hallucinations
Deterministic guardrails — raw calculations and drug IDs are managed strictly by backend code. Gemini is restricted to text translation, invoice parsing, and a bounded surge multiplier.

### Vendor Exclusion
Human-in-the-loop approval — every reorder requires a single confirmation tap from the PHC pharmacist before sending.

### Rural Intermittent Connectivity
Store-and-forward architecture — actions queue in IndexedDB while offline and sync automatically once connectivity is restored.

### AI Surge Model Failure
Multiplier is schema-validated and hard-capped at 1.0 *to 2.5. On any failure, the system falls back to a static seasonality matrix.

### Routing Unavailability
Provider chain falls back gracefully from Google Maps Routes -> OpenStreetMap OSRM -> Haversine straight-line calculation.

-------------------------------------------------------------------------------------------------------
Team
Shreyas: Backend Architecture, DB Models, Core Reorder Math, Seed Data Engine & REST API Gateway

Sandra: Gemini AI Integrations (Vision, Audio, Surge Multiplier, SMS Engine) & Road Routing Engine

Bhavana: PHC Worker App, Camera/Audio Capture UI, Offline Storage & Local Inventory View

Darren: District Admin Dashboard, Kanban Pipeline, Interactive Leaflet.js Map & Transfer Modal
------------------------------------------------------------------------------------------------------
Solving for India — built to scale from a single district to healthcare networks across states
