# PHC Replenishment Engine

**Autonomous Medicine Replenishment & Supply Chain Resilience Engine for Rural Primary Health Centres**

Built for [Build with AI: Code for Communities — Second Edition](https://buildwithai.devfolio.co) (Google Cloud hackathon) · Track: **Smart Health & Supply Chain Resilience**

---

## The Problem

Rural Primary Health Centres (PHCs) across India routinely run out of essential medicines — Paracetamol, ORS, antibiotics — while other batches expire unused a few shelves away. The root causes aren't a lack of medicine, they're operational:

- **Manual paper registers** cause delayed, error-prone stock updates
- **Reactive reordering** — vendors are contacted only after stock hits zero, ignoring delivery lead time
- **No cross-PHC visibility** — a neighboring PHC with surplus stock might as well be on another planet
- **Language and infrastructure gaps** between PHC staff, district warehouses, and local vendors

## The Solution

An AI system that moves from *passive dashboard* to *autonomous action*:

| Stage | What happens |
|---|---|
| **Capture** | PHC staff photograph a stock invoice or medicine carton. Gemini Vision extracts drug name, batch number, quantity, and expiry into structured JSON — no manual typing. |
| **Predict** | The system tracks consumption velocity per medicine and flags stock that will run out *before* the vendor's delivery lead time allows a safe reorder — not just when stock hits zero. |
| **Act** | Gemini Flash drafts a localized, natural-language reorder request and dispatches it to the vendor via SMS. |
| **Resolve** | If a vendor delivery is delayed, the system checks neighboring PHCs (within a 20 km radius) for surplus stock and proposes an emergency peer-to-peer transfer. |

Every AI-generated action — reorder or transfer — requires a single human confirmation tap before it's sent. Raw quantities and drug IDs are handled by deterministic backend code; Gemini is scoped strictly to parsing and translation, with JSON-schema validation on every call.

## Architecture

```
[ PHC Staff ] --(Gemini Vision OCR)--> [ Offline-First PWA ]
                                                |
                                       (Background Sync)
                                                v
[ District Vendor ] <--(SMS API)-- [ FastAPI Backend ] <--> [ PostgreSQL ]
         |                                     |
  (Status Updates)                    (Reorder & Transfer Logic)
         v                                     v
[ Live Tracking Dashboard ] <---------- [ Admin Web App ]
```

**Order lifecycle:** `Requisition Sent → Vendor Confirmed → In Transit → Delivered & Verified`

## Google AI Integration

| Touchpoint | Tool | Function |
|---|---|---|
| Document scanning | Gemini Vision API | Extracts batch, dosage, and expiry from invoice/packaging photos |
| Vendor communication | Gemini Flash API | Translates structured orders into localized, natural SMS text |
| Structured output | `response_mime_type="application/json"` + Pydantic validation | Prevents hallucinated quantities/drug IDs from reaching the database |

## Tech Stack

- **Backend:** FastAPI, PostgreSQL, Redis
- **AI:** Google Gemini 2.5 Flash (`google-genai` SDK), Gemini Vision
- **Frontend:** React (offline-first PWA with IndexedDB + Service Worker), Leaflet.js for the PHC network map
- **Messaging:** Twilio SMS
- **Deployment:** Cloud Run / Render (backend), Vercel (frontend)
- **Data:** Faker-generated synthetic dataset (50+ Indian PHCs, NLEM medicine codes)

## Repository Structure

```
phc-replenishment-engine/
├── backend/
│   ├── core/              # DB models, reorder math, inter-PHC distance logic, API routes
│   └── ai_integration/    # Gemini Vision, audio parsing, multilingual SMS engine
├── frontend/
│   ├── phc-app/           # PHC staff PWA — camera capture, voice logging, local stock view
│   └── admin-dashboard/   # District admin — order pipeline, PHC network map, transfer UI
├── data/                  # Synthetic seed data
├── docs/                  # Architecture notes, API contracts, pitch materials
└── README.md
```

## Team

| Role | Owner | Responsibility |
|---|---|---|
| Backend Dev 1 — System Architecture & Core Logic | Shreyas | DB schema, reorder math, inter-PHC distance calculations, API gateway |
| Backend Dev 2 — Google AI & Communications | Sandra | Gemini Vision integration, audio parsing, multilingual SMS engine |
| Frontend Dev 1 — PHC Mobile App / PWA | Bhavana | Staff-facing interface, camera/voice UI, local inventory view |
| Frontend Dev 2 — District Admin & Network Dashboard | Darren | Order pipeline, interactive PHC map, transfer UI |

## Getting Started

### Backend
```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn core.main:app --reload
```

### Frontend
```bash
cd frontend/phc-app   # or frontend/admin-dashboard
npm install
npm run dev
```

Environment variables (Gemini API key, Twilio credentials, database URL) go in a `.env` file — **never commit this**. See `.env.example` in each module once added.

## Submission Checklist (Build with AI — Code for Communities, 2nd Edition)

- [ ] Source code — this repository
- [ ] Demo video (3–5 min, end-to-end walkthrough)
- [ ] Pitch deck (10–12 slides)
- [ ] 2–3 line solution description
- [ ] Deployed live link
- [ ] Google AI integration clearly demonstrated (non-decorative)

---

Built for rural Indian PHCs. Designed to scale from one district to a national network.
