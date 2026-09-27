from backend.ai_integration.gemini_sms_engine import send_sms_fast2sms
import os
from dotenv import load_dotenv

load_dotenv()

# Put your actual 10-digit Indian mobile number here (no +91)
MY_PHONE = "YOUR_10_DIGIT_NUMBER"

print("Firing live test SMS via Fast2SMS Quick route...")
response = send_sms_fast2sms(
    phone_number=MY_PHONE,
    message="PHC Alert: Stock-out warning for Paracetamol 500mg. Immediate redistribution required.",
    dry_run=False
)

print("Test Result:", response)