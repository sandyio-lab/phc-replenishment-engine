"""
Gemini Surge Multiplier Module
================================
Estimates a short-term demand-surge multiplier for a PHC's drug consumption,
driven by season, district, and an optional free-text "reported signal"
(e.g. a health worker note about rising flu cases).

Applied BEFORE compute_reorder_point() so the reorder engine reacts to
predicted demand, not just historical average:

    surge = get_surge_multiplier(district=phc.district, reported_signal=note)
    adjusted_avg = apply_surge_to_avg_daily(item.avg_daily_consumption, surge)
    rop = compute_reorder_point(adjusted_avg, item.supplier_lead_days, item.safety_stock_days)

Single responsibility — same as gemini_vision_ocr.py and
gemini_audio_stock_update.py: does not touch the database, does not place
orders. Demo-safe: falls back to a deterministic seasonal table on any
Gemini failure instead of raising.
"""

import os
import json
import time
import random
import logging
from datetime import date
from typing import Optional, List

from pydantic import BaseModel, Field, ValidationError
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

MODEL_NAME = "gemini-3.6-flash"  # per team decision: 2.5-flash no longer available to new users

# --- Seasonal fallback table (also the offline/demo-safe path) ---
# month -> {drug_category: multiplier}. India-specific seasonality:
# monsoon (Jun-Sep) -> GI + respiratory; winter (Nov-Jan) -> respiratory.
SEASONAL_FALLBACK = {
    6:  {"respiratory": 1.4, "gi": 1.6, "default": 1.1},
    7:  {"respiratory": 1.5, "gi": 1.8, "default": 1.15},
    8:  {"respiratory": 1.5, "gi": 1.7, "default": 1.15},
    9:  {"respiratory": 1.3, "gi": 1.4, "default": 1.1},
    11: {"respiratory": 1.4, "gi": 1.1, "default": 1.1},
    12: {"respiratory": 1.6, "gi": 1.1, "default": 1.15},
    1:  {"respiratory": 1.5, "gi": 1.1, "default": 1.1},
}
DEFAULT_MULTIPLIER = 1.0


class SurgeAssessment(BaseModel):
    multiplier: float = Field(ge=1.0, le=2.5)
    affected_drug_categories: List[str] = Field(default_factory=list)
    rationale: str
    confidence: float = Field(ge=0.0, le=1.0)
    source: str = Field(default="gemini")  # "gemini" | "seasonal_fallback"


def _seasonal_fallback(district: str, month: int, drug_category: str = "default") -> SurgeAssessment:
    table = SEASONAL_FALLBACK.get(month, {})
    multiplier = table.get(drug_category, table.get("default", DEFAULT_MULTIPLIER))
    return SurgeAssessment(
        multiplier=multiplier,
        affected_drug_categories=[drug_category] if multiplier > 1.0 else [],
        rationale=f"Seasonal baseline for month={month}, district={district} (no live signal / API unavailable).",
        confidence=0.5,
        source="seasonal_fallback",
    )


def get_surge_multiplier(
    district: str,
    month: Optional[int] = None,
    reported_signal: Optional[str] = None,
    drug_category: str = "default",
    max_retries: int = 3,
) -> SurgeAssessment:
    """
    Returns a SurgeAssessment with a consumption multiplier for the given
    district/month, optionally reasoning over a free-text reported_signal.
    Falls back to the deterministic seasonal table on any API failure.
    """
    month = month or date.today().month
    api_key = (os.getenv("GEMINI_API_KEY") or "").strip() or (os.getenv("GOOGLE_API_KEY") or "").strip()
    if not api_key:
        logger.warning("GEMINI_API_KEY not set — using seasonal fallback.")
        return _seasonal_fallback(district, month, drug_category)

    prompt = f"""You are assisting a rural Indian Primary Health Centre supply chain system.

Given:
- District: {district}
- Month: {month}
- Reported signal (may be empty): "{reported_signal or 'none reported'}"

Estimate a short-term demand SURGE MULTIPLIER (1.0 to 2.5) for medicine
consumption at this PHC, based on Indian seasonal epidemiology (e.g. monsoon
GI/respiratory illness, winter respiratory illness) and the reported signal
if present. 1.0 means no surge expected.

Return ONLY JSON matching this schema, no other text:
{{
  "multiplier": float (1.0-2.5),
  "affected_drug_categories": [string, ...],
  "rationale": string (1-2 sentences, India-specific reasoning),
  "confidence": float (0.0-1.0)
}}"""

    last_error = None
    for attempt in range(max_retries):
        try:
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.2,
                ),
            )
            data = json.loads(response.text)
            data["source"] = "gemini"
            return SurgeAssessment(**data)

        except (ValidationError, json.JSONDecodeError, KeyError) as e:
            logger.error("Surge multiplier: malformed Gemini response (attempt %d): %s", attempt + 1, e)
            last_error = e
        except Exception as e:  # network / API errors
            logger.error("Surge multiplier: Gemini call failed (attempt %d): %s", attempt + 1, e)
            last_error = e

        if attempt < max_retries - 1:
            time.sleep((2 ** attempt) + random.uniform(0, 0.5))

    logger.warning("Surge multiplier: all %d attempts failed (%s) — using seasonal fallback.", max_retries, last_error)
    return _seasonal_fallback(district, month, drug_category)


def apply_surge_to_avg_daily(avg_daily_consumption: float, surge: SurgeAssessment) -> float:
    """Apply the multiplier to a raw avg_daily_consumption value."""
    return round(avg_daily_consumption * surge.multiplier, 2)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = get_surge_multiplier(
        district="Pune",
        month=8,
        reported_signal="flu cases rising in Velhe block",
        drug_category="respiratory",
    )
    print(result.model_dump_json(indent=2))
