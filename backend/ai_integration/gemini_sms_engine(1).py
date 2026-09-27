"""
gemini_sms_engine.py
----------------------
Backend Dev 2 — Item 3: Multilingual SMS Engine

Purpose
=======
Take a "Low Stock" alert (drug, quantity left, vendor, vendor's phone and
preferred language) and:
  1. Ask Gemini to turn it into a natural, polite reorder message in the
     vendor's regional language (not a robotic word-for-word translation).
  2. Send that message as a real SMS via Fast2SMS's Quick (`q`) route
     REST API (raw `requests` calls, no SDK dependency).
  3. Return a structured record of what was composed and what happened,
     shaped for Backend Dev 1 to log against the order.

Same single-responsibility rule as the other two modules: this file does
not decide WHETHER to reorder (that's Backend Dev 1's dynamic-reorder
logic) and does not touch the database directly.

SAFETY DEFAULT: dispatch_low_stock_alert() defaults to dry_run=True. It
will NOT send a real SMS or spend Fast2SMS credit unless you explicitly
pass dry_run=False. See 03_GEMINI_SMS_SETUP.md for why.

Why Fast2SMS instead of Twilio
===============================
Twilio's trial tier requires pre-registered/predefined SMS templates for
Indian numbers (TRAI DLT compliance) and free-text messages get rejected
with "Invalid template name." Fast2SMS's Quick (`q`) route sends through
their own pre-approved shared route, so it accepts free-text messages to
real Indian numbers without you needing your own DLT template
registration. It's meant for testing/low-volume use (a hackathon demo),
not production bulk SMS — that would need a DLT-registered route later.

Usage
=====
    from gemini_sms_engine import LowStockAlert, dispatch_low_stock_alert

    alert = LowStockAlert(
        phc_name="Kadugodi PHC",
        drug_name="Paracetamol 500mg",
        current_stock=12,
        unit="strips",
        reorder_quantity=200,
        vendor_name="Karnataka State Medical Supplies Corp",
        vendor_phone="9876543210",
        target_language="Kannada",
    )

    result = dispatch_low_stock_alert(alert, dry_run=True)   # preview only
    print(result.model_dump_json(indent=2))

    # result = dispatch_low_stock_alert(alert, dry_run=False)  # actually sends

Or from the command line (uses a built-in sample alert):
    python gemini_sms_engine.py            # dry run — prints what would be sent
    python gemini_sms_engine.py --send      # actually sends the SMS

Environment
===========
    GEMINI_API_KEY=your_gemini_key_here
    FAST2SMS_API_KEY=your_fast2sms_key_here

Install
=======
    pip install google-genai pydantic python-dotenv requests
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from typing import Optional

import requests
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel, Field, ValidationError

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("gemini_sms_engine")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

MODEL_NAME = "gemini-2.5-flash"
MAX_RETRIES = 2
RETRY_BACKOFF_SECONDS = 1.5

FAST2SMS_URL = "https://www.fast2sms.com/dev/bulkV2"

_GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
_FAST2SMS_API_KEY = os.environ.get("FAST2SMS_API_KEY")

if not _GEMINI_API_KEY:
    logger.warning("GEMINI_API_KEY not set. Message composition will fail until it is.")
if not _FAST2SMS_API_KEY:
    logger.warning(
        "FAST2SMS_API_KEY not set. dry_run mode will still work; real sending will not."
    )

_client: Optional[genai.Client] = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=_GEMINI_API_KEY)
    return _client


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class LowStockAlert(BaseModel):
    """Input — what Backend Dev 1's system hands off when stock is low."""
    phc_name: str
    drug_name: str
    current_stock: int
    unit: str = "units"
    reorder_quantity: int = 0
    vendor_name: str
    vendor_phone: str = Field(description="Indian mobile number in any common form, e.g. '9876543210', '+919876543210', or '919876543210'")
    target_language: str = Field(default="English", description="e.g. 'Hindi', 'Kannada', 'Tamil', 'Telugu', 'English'")


class ReorderMessage(BaseModel):
    """Gemini's composed message — schema-enforced."""
    local_message: str = Field(description="The polite reorder request, written naturally in target_language (native script, not transliteration, unless target_language is English).")
    english_back_translation: str = Field(description="Plain English back-translation of local_message, so a non-speaker can sanity-check what's being sent.")
    language: str = Field(description="The language local_message is actually written in.")
    notes: str = Field(default="", description="Any caveats about the composition. Empty string if none.")


class DispatchResult(BaseModel):
    """Output — what gets logged against the order."""
    phc_name: str
    drug_name: str
    vendor_name: str
    vendor_phone: str
    local_message: str
    english_back_translation: str
    language: str
    char_count: int
    dry_run: bool
    sent: bool
    provider: str = "fast2sms"
    message_sid: str = ""
    error: str = ""


# ---------------------------------------------------------------------------
# Fallback — used only if the Gemini composition call fails after retries.
# Plain English so the vendor still gets something actionable.
# ---------------------------------------------------------------------------

def _fallback_message(alert: LowStockAlert) -> ReorderMessage:
    text = (
        f"Dear {alert.vendor_name}, this is {alert.phc_name}. "
        f"Our stock of {alert.drug_name} is low ({alert.current_stock} {alert.unit} remaining). "
        f"Please arrange delivery of {alert.reorder_quantity} {alert.unit} at the earliest. Thank you."
    )
    return ReorderMessage(
        local_message=text,
        english_back_translation=text,
        language="English",
        notes="FALLBACK MESSAGE — live Gemini composition failed; plain English template used instead.",
    )


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

_SYSTEM_INSTRUCTION = """You compose short, polite SMS reorder requests from a rural Indian \
Primary Health Centre (PHC) to a local medicine vendor.

Rules:
1. Write a natural, respectful message a real vendor would read and act on — not a robotic \
field-by-field translation of the data. Vendors in this context respond better to a courteous, \
human-sounding request than a terse data dump.
2. Write local_message in the requested target_language, in its native script (e.g. actual \
Devanagari for Hindi, actual Kannada script for Kannada) — not English transliteration — unless \
target_language is English.
3. Keep it concise enough for a single SMS (roughly under 300 characters where the language and \
politeness norms allow it).
4. Always include: the PHC name, the medicine name, and the quantity needed. Do not invent details \
not present in the input.
5. Always also provide english_back_translation — a plain English translation of exactly what \
local_message says, so someone who can't read the target script can verify nothing was distorted.
6. Output must match the provided JSON schema exactly. No prose, no markdown, no commentary \
outside the JSON."""


# ---------------------------------------------------------------------------
# Step 1: compose the localized message
# ---------------------------------------------------------------------------

def compose_reorder_message(alert: LowStockAlert, use_fallback_on_failure: bool = True) -> ReorderMessage:
    """
    Ask Gemini to turn a LowStockAlert into a natural, polite reorder SMS in
    the vendor's preferred language, with an English back-translation for
    verification.
    """
    prompt_payload = alert.model_dump()
    last_error: Optional[Exception] = None

    for attempt in range(1, MAX_RETRIES + 2):
        try:
            client = _get_client()
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=[
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_text(
                                text=f"Compose a reorder SMS from this alert data:\n{json.dumps(prompt_payload, ensure_ascii=False)}"
                            ),
                        ],
                    )
                ],
                config=types.GenerateContentConfig(
                    system_instruction=_SYSTEM_INSTRUCTION,
                    response_mime_type="application/json",
                    response_schema=ReorderMessage,
                    temperature=0.4,  # a little room for natural phrasing, still low
                ),
            )

            data = json.loads(response.text)
            result = ReorderMessage.model_validate(data)
            logger.info("Message composed on attempt %d (%s, %d chars).", attempt, result.language, len(result.local_message))
            return result

        except (ValidationError, json.JSONDecodeError) as e:
            last_error = e
            logger.warning("Attempt %d: schema validation failed (%s). Retrying...", attempt, e)
        except Exception as e:
            last_error = e
            logger.warning("Attempt %d: API call failed (%s). Retrying...", attempt, e)

        if attempt <= MAX_RETRIES:
            time.sleep(RETRY_BACKOFF_SECONDS * attempt)

    logger.error("All %d composition attempts failed. Last error: %s", MAX_RETRIES + 1, last_error)

    if use_fallback_on_failure:
        logger.warning("Using plain-English fallback message so the vendor still gets something actionable.")
        return _fallback_message(alert)

    raise RuntimeError(f"Gemini message composition failed after {MAX_RETRIES + 1} attempts") from last_error


# ---------------------------------------------------------------------------
# Step 2: normalize phone number & send via Fast2SMS Quick route (raw requests)
# ---------------------------------------------------------------------------

def _normalize_to_indian_10_digit(raw_number: str) -> str:
    """
    Fast2SMS's `numbers` param wants a bare 10-digit Indian mobile number —
    no '+', no country code. This strips a leading '+91' or bare '91'
    prefix (people copying numbers from the Twilio/E.164 days will have
    these) and leaves the last 10 digits.
    """
    digits = "".join(ch for ch in raw_number if ch.isdigit())

    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 13 and digits.startswith("091"):
        digits = digits[3:]

    if len(digits) > 10:
        digits = digits[-10:]

    return digits


def send_sms_fast2sms(
    phone_number: str,
    message: str,
    dry_run: bool = True,
    api_key: Optional[str] = None,
) -> dict:
    """
    Sends an SMS via Fast2SMS's Quick (`q`) route.

    phone_number: any common form ('9876543210', '+919876543210',
        '919876543210') — normalized to a bare 10-digit number internally.
    message: the text to send (should already be composed/localized).
    dry_run: if True (default), composes the request but does not call
        Fast2SMS or spend credit. Returns a preview dict instead.
    api_key: Fast2SMS API key. Defaults to FAST2SMS_API_KEY from the
        environment if not passed explicitly.

    Returns a dict: {"sent": bool, "message_sid": str, "error": str}
    ("message_sid" holds Fast2SMS's request_id when available, kept under
    that name so DispatchResult's shape doesn't change across providers.)
    """
    clean_number = _normalize_to_indian_10_digit(phone_number)
    key = api_key or _FAST2SMS_API_KEY

    if dry_run:
        logger.info("[DRY RUN] Would send via Fast2SMS to %s: %s", clean_number, message)
        return {"sent": False, "message_sid": "", "error": ""}

    if not key:
        return {"sent": False, "message_sid": "", "error": "FAST2SMS_API_KEY not configured"}

    if len(clean_number) != 10:
        return {
            "sent": False,
            "message_sid": "",
            "error": f"'{phone_number}' did not normalize to a valid 10-digit Indian number (got '{clean_number}')",
        }

    payload = {
        "route": "q",
        "message": message,
        "language": "english",
        "flash": 0,
        "numbers": clean_number,
    }
    headers = {
        "authorization": key,
        "Content-Type": "application/x-www-form-urlencoded",
    }

    try:
        response = requests.post(FAST2SMS_URL, data=payload, headers=headers, timeout=15)
        response.raise_for_status()
        result = response.json()

        if result.get("return") is True:
            return {
                "sent": True,
                "message_sid": str(result.get("request_id", "")),
                "error": "",
            }
        return {
            "sent": False,
            "message_sid": "",
            "error": "; ".join(result.get("message", ["Unknown Fast2SMS error"]))
            if isinstance(result.get("message"), list)
            else str(result.get("message", "Unknown Fast2SMS error")),
        }

    except requests.RequestException as e:
        return {"sent": False, "message_sid": "", "error": str(e)}
    except (ValueError, json.JSONDecodeError) as e:
        return {"sent": False, "message_sid": "", "error": f"Could not parse Fast2SMS response: {e}"}


# ---------------------------------------------------------------------------
# Public entry point: compose + (optionally) send
# ---------------------------------------------------------------------------

def dispatch_low_stock_alert(alert: LowStockAlert, dry_run: bool = True) -> DispatchResult:
    """
    Compose the localized reorder message and, unless dry_run is True
    (the default), send it as a real SMS via Fast2SMS.

    dry_run=True (default): composes and returns the message, does NOT
        send anything or touch Fast2SMS credit. Use this to review what
        would be sent before committing.
    dry_run=False: actually sends the SMS. Requires FAST2SMS_API_KEY in
        your environment.
    """
    composed = compose_reorder_message(alert)
    clean_number = _normalize_to_indian_10_digit(alert.vendor_phone)

    send_outcome = send_sms_fast2sms(
        phone_number=alert.vendor_phone,
        message=composed.local_message,
        dry_run=dry_run,
    )

    if not dry_run:
        if send_outcome["sent"]:
            logger.info("SMS sent to %s (request_id: %s).", clean_number, send_outcome["message_sid"])
        else:
            logger.error("SMS send failed to %s: %s", clean_number, send_outcome["error"])

    return DispatchResult(
        phc_name=alert.phc_name,
        drug_name=alert.drug_name,
        vendor_name=alert.vendor_name,
        vendor_phone=clean_number,
        local_message=composed.local_message,
        english_back_translation=composed.english_back_translation,
        language=composed.language,
        char_count=len(composed.local_message),
        dry_run=dry_run,
        sent=send_outcome["sent"],
        message_sid=send_outcome["message_sid"],
        error=send_outcome["error"],
    )


# ---------------------------------------------------------------------------
# CLI entry point — uses a built-in sample alert so you can test with no args
# ---------------------------------------------------------------------------

_SAMPLE_ALERT = LowStockAlert(
    phc_name="Kadugodi PHC",
    drug_name="Paracetamol 500mg",
    current_stock=12,
    unit="strips",
    reorder_quantity=200,
    vendor_name="Karnataka State Medical Supplies Corp",
    vendor_phone="9876543210",   # replace with your own number to test a real send
    target_language="Kannada",
)

if __name__ == "__main__":
    send_for_real = "--send" in sys.argv

    if send_for_real:
        print("Sending a REAL SMS via Fast2SMS (dry_run=False)...\n")
    else:
        print("Dry run (default) — nothing will be sent. Pass --send to actually deliver.\n")

    result = dispatch_low_stock_alert(_SAMPLE_ALERT, dry_run=not send_for_real)
    print(result.model_dump_json(indent=2))