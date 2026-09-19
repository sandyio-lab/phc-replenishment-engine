# PHC Replenishment Engine

This workspace is now one FastAPI application combining:

- Backend 1: SQLite/PostgreSQL models, seed data, reorder-point logic, PHC distance and transfer suggestions, inventory, vendor, order, and analytics APIs.
- Backend 2: Gemini invoice OCR, voice stock extraction, and multilingual reorder-message adapters.
- Frontend 1: PHC worker console at `/worker`.
- Frontend 2: district supply-chain dashboard at `/`.

## Run locally

From this directory:

```bash
/usr/local/bin/python3 -m pip install -r requirements.txt
/usr/local/bin/python3 seed.py --reset
/usr/local/bin/python3 -m uvicorn app.main:app --reload --port 8000
```

Open `http://localhost:8000/` for the district dashboard, `http://localhost:8000/worker` for the PHC worker app, and `http://localhost:8000/docs` for the API.

## AI credentials

Create `.env` from `.env.example` and set `GEMINI_API_KEY`. The app still returns validated demo fallback data when Gemini is unavailable, so the core workflow remains demonstrable. Add `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, and `TWILIO_FROM_NUMBER` only when real SMS delivery is required. The reorder-message endpoint is a dry run by default.

## End-to-end flow

1. Seeded PHC inventory is loaded by the worker app through `/api/v1/phcs/{id}/inventory`.
2. A worker records a receipt or dispensing event; the app persists the new quantity through `/api/v1/inventory` or `/api/v1/inventory/{id}`.
3. Invoice photos and voice notes are sent to `/api/v1/ai/invoice` and `/api/v1/ai/audio`; structured output prefills the worker form.
4. The demand engine exposes alerts at `/api/v1/phcs/{id}/alerts` and can create replenishment orders with `/api/v1/orders/auto-generate/{id}`.
5. The district dashboard reads PHC health from `/api/v1/analytics/network-map` and orders from `/api/v1/orders`.
6. Orders advance through `draft -> requisition_sent -> vendor_confirmed -> in_transit -> delivered -> verified` using `/api/v1/orders/{id}/status`.
7. A localized SMS can be previewed with `/api/v1/ai/reorder-message`; pass `send: true` only after Twilio credentials are configured.