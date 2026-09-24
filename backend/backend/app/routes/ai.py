"""HTTP adapters for the Gemini integrations owned by Backend 2."""

from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

router = APIRouter(prefix="/ai", tags=["Google AI"])


class ReorderPreviewRequest(BaseModel):
    phc_name: str
    drug_name: str
    current_stock: int = Field(ge=0)
    unit: str = "units"
    reorder_quantity: int = Field(ge=0)
    vendor_name: str
    vendor_phone: str
    target_language: str = "English"
    send: bool = False


@router.post("/invoice")
async def extract_invoice(file: UploadFile = File(...)):
    """Extract structured medicine lines from an uploaded invoice photo."""
    content_type = (file.content_type or "").split(";", 1)[0]
    if content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise HTTPException(status_code=415, detail="Upload a JPEG, PNG, or WebP image.")

    from ai_integration.gemini_vision_ocr import extract_invoice_data

    try:
        result = extract_invoice_data(
            await file.read(),
            mime_type=content_type,
            use_fallback_on_failure=False,
        )
    except RuntimeError as error:
        message = str(error)
        if "401" in message or "UNAUTHENTICATED" in message:
            detail = "Gemini rejected the API key. Check GEMINI_API_KEY or GOOGLE_API_KEY in ai_integration/.env."
        elif "429" in message or "RESOURCE_EXHAUSTED" in message:
            detail = "Gemini quota is exhausted. Check the Gemini project quota and billing."
        else:
            detail = "Gemini photo extraction failed. Check the API key, quota, model availability, and image format."
        return JSONResponse(
            status_code=500,
            content={
                "error": "gemini_invoice_extraction_failed",
                "detail": detail,
            },
        )
    return result.model_dump(mode="json")


@router.post("/audio")
async def extract_audio(
    file: UploadFile = File(...),
    mime_type: str | None = Form(None),
):
    """Transcribe a PHC voice note and return validated stock movements."""
    content_type = (mime_type or file.content_type or "audio/wav").split(";", 1)[0]
    if not content_type.startswith("audio/"):
        raise HTTPException(status_code=415, detail="Upload an audio recording.")

    from ai_integration.gemini_audio_stock_update import extract_stock_updates

    try:
        result = extract_stock_updates(
            await file.read(),
            mime_type=content_type,
            use_fallback_on_failure=False,
        )
    except RuntimeError as error:
        message = str(error)
        if "401" in message or "UNAUTHENTICATED" in message:
            detail = "Gemini rejected the API key. Check GEMINI_API_KEY in ai_integration/.env."
        elif "429" in message or "RESOURCE_EXHAUSTED" in message:
            detail = "Gemini quota is exhausted. Check the Gemini project quota and billing."
        else:
            detail = "Gemini audio extraction failed. Check the API key, quota, model availability, and audio format."
        raise HTTPException(
            status_code=503,
            detail=detail,
        ) from error
    return result.model_dump(mode="json")


@router.post("/reorder-message")
def create_reorder_message(payload: ReorderPreviewRequest):
    """Compose a localized reorder SMS, dry-running unless `send` is true."""
    from ai_integration.gemini_sms_engine import LowStockAlert, dispatch_low_stock_alert

    alert = LowStockAlert(
        phc_name=payload.phc_name,
        drug_name=payload.drug_name,
        current_stock=payload.current_stock,
        unit=payload.unit,
        reorder_quantity=payload.reorder_quantity,
        vendor_name=payload.vendor_name,
        vendor_phone=payload.vendor_phone,
        target_language=payload.target_language,
    )
    result = dispatch_low_stock_alert(alert, dry_run=not payload.send)
    return result.model_dump(mode="json")