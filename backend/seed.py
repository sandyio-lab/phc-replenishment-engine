"""
Data Seeding Script — PHC Supply Chain
=======================================
Populates the database with:
  • 55 real-ish Indian PHCs across 5 Maharashtra districts
  • 10 district vendors (one primary + one backup per district)
  • 30 NLEM 2022 essential medicines per PHC  (~1 650 inventory rows)
  • ~200 synthetic orders in various pipeline states

Run from the backend/ directory:
    python seed.py

Supports --reset flag to wipe and reseed:
    python seed.py --reset
"""

import argparse
import random
import sys
from datetime import date, timedelta
from pathlib import Path

# Make sure imports resolve when run directly from backend/
sys.path.insert(0, str(Path(__file__).parent))

from app.core.database import engine, SessionLocal, Base
from app.models.phc       import PHC
from app.models.inventory import InventoryItem, StockStatus
from app.models.vendor    import Vendor
from app.models.order     import Order, OrderStatus, OrderType
from app.core.demand_engine import compute_reorder_point, classify_stock_status

random.seed(42)   # reproducible synthetic data

# ─────────────────────────────────────────────────────────────────────────────
# MASTER DATA — PHCs
# Real district + block names; lat/lon nudged to simulate cluster geography
# ─────────────────────────────────────────────────────────────────────────────

PHC_MASTER = [
    # ── Pune district ──────────────────────────────────────────────────────
    {"name": "PHC Velhe",        "phc_code": "PHC-PUN-001", "district": "Pune",    "block": "Velhe",      "village": "Velhe",      "lat": 18.2661, "lon": 73.6514, "lang": "Marathi"},
    {"name": "PHC Mulshi",       "phc_code": "PHC-PUN-002", "district": "Pune",    "block": "Mulshi",     "village": "Paud",       "lat": 18.5204, "lon": 73.5943, "lang": "Marathi"},
    {"name": "PHC Bhor",         "phc_code": "PHC-PUN-003", "district": "Pune",    "block": "Bhor",       "village": "Bhor",       "lat": 18.1500, "lon": 73.8500, "lang": "Marathi"},
    {"name": "PHC Mawal",        "phc_code": "PHC-PUN-004", "district": "Pune",    "block": "Mawal",      "village": "Talegaon",   "lat": 18.7270, "lon": 73.6740, "lang": "Marathi"},
    {"name": "PHC Ambegaon",     "phc_code": "PHC-PUN-005", "district": "Pune",    "block": "Ambegaon",   "village": "Ghodegaon",  "lat": 19.0900, "lon": 73.7600, "lang": "Marathi"},
    {"name": "PHC Junnar",       "phc_code": "PHC-PUN-006", "district": "Pune",    "block": "Junnar",     "village": "Junnar",     "lat": 19.2080, "lon": 73.8820, "lang": "Marathi"},
    {"name": "PHC Shirur",       "phc_code": "PHC-PUN-007", "district": "Pune",    "block": "Shirur",     "village": "Shirur",     "lat": 18.8280, "lon": 74.3680, "lang": "Marathi"},
    {"name": "PHC Daund",        "phc_code": "PHC-PUN-008", "district": "Pune",    "block": "Daund",      "village": "Daund",      "lat": 18.4610, "lon": 74.5830, "lang": "Marathi"},
    {"name": "PHC Indapur",      "phc_code": "PHC-PUN-009", "district": "Pune",    "block": "Indapur",    "village": "Indapur",    "lat": 18.1080, "lon": 75.0290, "lang": "Marathi"},
    {"name": "PHC Baramati",     "phc_code": "PHC-PUN-010", "district": "Pune",    "block": "Baramati",   "village": "Baramati",   "lat": 18.1530, "lon": 74.5820, "lang": "Marathi"},
    {"name": "PHC Purandar",     "phc_code": "PHC-PUN-011", "district": "Pune",    "block": "Purandar",   "village": "Saswad",     "lat": 18.3370, "lon": 74.0200, "lang": "Marathi"},

    # ── Nashik district ────────────────────────────────────────────────────
    {"name": "PHC Igatpuri",     "phc_code": "PHC-NSK-001", "district": "Nashik",  "block": "Igatpuri",   "village": "Igatpuri",   "lat": 19.6942, "lon": 73.5619, "lang": "Marathi"},
    {"name": "PHC Trimbakeshwar","phc_code": "PHC-NSK-002", "district": "Nashik",  "block": "Trimbak",    "village": "Trimbak",    "lat": 19.9337, "lon": 73.5302, "lang": "Marathi"},
    {"name": "PHC Peth",         "phc_code": "PHC-NSK-003", "district": "Nashik",  "block": "Peth",       "village": "Peth",       "lat": 20.0900, "lon": 73.7300, "lang": "Marathi"},
    {"name": "PHC Surgana",      "phc_code": "PHC-NSK-004", "district": "Nashik",  "block": "Surgana",    "village": "Surgana",    "lat": 20.5560, "lon": 73.6120, "lang": "Marathi"},
    {"name": "PHC Kalwan",       "phc_code": "PHC-NSK-005", "district": "Nashik",  "block": "Kalwan",     "village": "Kalwan",     "lat": 20.5170, "lon": 74.0110, "lang": "Marathi"},
    {"name": "PHC Nandgaon",     "phc_code": "PHC-NSK-006", "district": "Nashik",  "block": "Nandgaon",   "village": "Nandgaon",   "lat": 20.3120, "lon": 74.6570, "lang": "Marathi"},
    {"name": "PHC Sinnar",       "phc_code": "PHC-NSK-007", "district": "Nashik",  "block": "Sinnar",     "village": "Sinnar",     "lat": 19.8520, "lon": 74.0010, "lang": "Marathi"},
    {"name": "PHC Baglan",       "phc_code": "PHC-NSK-008", "district": "Nashik",  "block": "Baglan",     "village": "Satana",     "lat": 20.5940, "lon": 74.2060, "lang": "Marathi"},
    {"name": "PHC Yeola",        "phc_code": "PHC-NSK-009", "district": "Nashik",  "block": "Yeola",      "village": "Yeola",      "lat": 20.0430, "lon": 74.4900, "lang": "Marathi"},
    {"name": "PHC Dindori",      "phc_code": "PHC-NSK-010", "district": "Nashik",  "block": "Dindori",    "village": "Dindori",    "lat": 19.9800, "lon": 73.8290, "lang": "Marathi"},

    # ── Aurangabad district ────────────────────────────────────────────────
    {"name": "PHC Gangapur",     "phc_code": "PHC-AUR-001", "district": "Aurangabad","block": "Gangapur",  "village": "Gangapur",   "lat": 19.6980, "lon": 75.0100, "lang": "Marathi"},
    {"name": "PHC Sillod",       "phc_code": "PHC-AUR-002", "district": "Aurangabad","block": "Sillod",    "village": "Sillod",     "lat": 20.1060, "lon": 75.6560, "lang": "Marathi"},
    {"name": "PHC Kannad",       "phc_code": "PHC-AUR-003", "district": "Aurangabad","block": "Kannad",    "village": "Kannad",     "lat": 20.2650, "lon": 75.1370, "lang": "Marathi"},
    {"name": "PHC Vaijapur",     "phc_code": "PHC-AUR-004", "district": "Aurangabad","block": "Vaijapur",  "village": "Vaijapur",   "lat": 19.9250, "lon": 74.7110, "lang": "Marathi"},
    {"name": "PHC Khuldabad",    "phc_code": "PHC-AUR-005", "district": "Aurangabad","block": "Khuldabad", "village": "Khuldabad",  "lat": 20.0580, "lon": 75.1990, "lang": "Marathi"},
    {"name": "PHC Paithan",      "phc_code": "PHC-AUR-006", "district": "Aurangabad","block": "Paithan",   "village": "Paithan",    "lat": 19.4750, "lon": 75.3880, "lang": "Marathi"},
    {"name": "PHC Phulambri",    "phc_code": "PHC-AUR-007", "district": "Aurangabad","block": "Phulambri", "village": "Phulambri",  "lat": 19.8760, "lon": 75.2630, "lang": "Marathi"},
    {"name": "PHC Soegaon",      "phc_code": "PHC-AUR-008", "district": "Aurangabad","block": "Soegaon",   "village": "Soegaon",    "lat": 20.4230, "lon": 75.9040, "lang": "Marathi"},

    # ── Latur district ─────────────────────────────────────────────────────
    {"name": "PHC Udgir",        "phc_code": "PHC-LAT-001", "district": "Latur",   "block": "Udgir",      "village": "Udgir",      "lat": 18.3930, "lon": 77.1170, "lang": "Marathi"},
    {"name": "PHC Ausa",         "phc_code": "PHC-LAT-002", "district": "Latur",   "block": "Ausa",       "village": "Ausa",       "lat": 18.2580, "lon": 76.5120, "lang": "Marathi"},
    {"name": "PHC Nilanga",      "phc_code": "PHC-LAT-003", "district": "Latur",   "block": "Nilanga",    "village": "Nilanga",    "lat": 17.7790, "lon": 76.7580, "lang": "Marathi"},
    {"name": "PHC Chakur",       "phc_code": "PHC-LAT-004", "district": "Latur",   "block": "Chakur",     "village": "Chakur",     "lat": 17.8820, "lon": 76.5640, "lang": "Marathi"},
    {"name": "PHC Renapur",      "phc_code": "PHC-LAT-005", "district": "Latur",   "block": "Renapur",    "village": "Renapur",    "lat": 18.0900, "lon": 76.5920, "lang": "Marathi"},
    {"name": "PHC Shirur Anantpal","phc_code":"PHC-LAT-006", "district": "Latur",  "block": "Shirur",     "village": "Shirur",     "lat": 17.9240, "lon": 76.9470, "lang": "Marathi"},
    {"name": "PHC Deoni",        "phc_code": "PHC-LAT-007", "district": "Latur",   "block": "Deoni",      "village": "Deoni",      "lat": 17.9800, "lon": 77.5980, "lang": "Marathi"},
    {"name": "PHC Jalkot",       "phc_code": "PHC-LAT-008", "district": "Latur",   "block": "Jalkot",     "village": "Jalkot",     "lat": 18.6110, "lon": 77.2430, "lang": "Marathi"},

    # ── Amravati district ──────────────────────────────────────────────────
    {"name": "PHC Achalpur",     "phc_code": "PHC-AMR-001", "district": "Amravati","block": "Achalpur",   "village": "Achalpur",   "lat": 21.2570, "lon": 77.5100, "lang": "Marathi"},
    {"name": "PHC Chandurbazar", "phc_code": "PHC-AMR-002", "district": "Amravati","block": "Chandurbazar","village": "Chandurbazar","lat": 20.8490,"lon": 77.7660, "lang": "Marathi"},
    {"name": "PHC Daryapur",     "phc_code": "PHC-AMR-003", "district": "Amravati","block": "Daryapur",   "village": "Daryapur",   "lat": 20.9200, "lon": 77.3240, "lang": "Marathi"},
    {"name": "PHC Warud",        "phc_code": "PHC-AMR-004", "district": "Amravati","block": "Warud",      "village": "Warud",      "lat": 21.4670, "lon": 78.2720, "lang": "Marathi"},
    {"name": "PHC Morshi",       "phc_code": "PHC-AMR-005", "district": "Amravati","block": "Morshi",     "village": "Morshi",     "lat": 21.3290, "lon": 77.9750, "lang": "Marathi"},
    {"name": "PHC Nandgaon Khandeshwar","phc_code":"PHC-AMR-006","district":"Amravati","block":"Nandgaon Kh.","village":"Nandgaon","lat":20.7940,"lon":77.3660,"lang":"Marathi"},
    {"name": "PHC Tiwsa",        "phc_code": "PHC-AMR-007", "district": "Amravati","block": "Tiwsa",      "village": "Tiwsa",      "lat": 21.0670, "lon": 77.6910, "lang": "Marathi"},
    {"name": "PHC Dharni",       "phc_code": "PHC-AMR-008", "district": "Amravati","block": "Dharni",     "village": "Dharni",     "lat": 21.3670, "lon": 76.9800, "lang": "Marathi"},
    {"name": "PHC Chikhaldara",  "phc_code": "PHC-AMR-009", "district": "Amravati","block": "Chikhaldara","village": "Chikhaldara","lat": 21.4040, "lon": 77.3050, "lang": "Marathi"},
    {"name": "PHC Anjangaon Surji","phc_code":"PHC-AMR-010","district": "Amravati","block": "Anjangaon",  "village": "Anjangaon",  "lat": 21.1660, "lon": 77.3090, "lang": "Marathi"},
]

# ─────────────────────────────────────────────────────────────────────────────
# MASTER DATA — VENDORS (2 per district)
# ─────────────────────────────────────────────────────────────────────────────

VENDOR_MASTER = [
    {"name": "Pune District Medical Stores",     "code": "VND-PUN-01", "district": "Pune",      "phone": "9822001001", "lang": "Marathi", "lead_days": 5},
    {"name": "Shivaji Pharma Distributors Pune", "code": "VND-PUN-02", "district": "Pune",      "phone": "9822001002", "lang": "Marathi", "lead_days": 7},
    {"name": "Nashik Arogya Bhandar",            "code": "VND-NSK-01", "district": "Nashik",    "phone": "9823002001", "lang": "Marathi", "lead_days": 6},
    {"name": "Trimurti Medical Nashik",          "code": "VND-NSK-02", "district": "Nashik",    "phone": "9823002002", "lang": "Marathi", "lead_days": 8},
    {"name": "Marathwada Pharma Aurangabad",     "code": "VND-AUR-01", "district": "Aurangabad","phone": "9824003001", "lang": "Marathi", "lead_days": 7},
    {"name": "Chhatrapati Medical Supplies",     "code": "VND-AUR-02", "district": "Aurangabad","phone": "9824003002", "lang": "Marathi", "lead_days": 9},
    {"name": "Latur Health Distributors",        "code": "VND-LAT-01", "district": "Latur",     "phone": "9825004001", "lang": "Marathi", "lead_days": 6},
    {"name": "Siddheshwar Medical Latur",        "code": "VND-LAT-02", "district": "Latur",     "phone": "9825004002", "lang": "Marathi", "lead_days": 8},
    {"name": "Vidarbha Pharma Amravati",         "code": "VND-AMR-01", "district": "Amravati",  "phone": "9826005001", "lang": "Marathi", "lead_days": 7},
    {"name": "Amravati District Drug Store",     "code": "VND-AMR-02", "district": "Amravati",  "phone": "9826005002", "lang": "Marathi", "lead_days": 9},
]

# ─────────────────────────────────────────────────────────────────────────────
# MASTER DATA — NLEM 2022 MEDICINES (30 items)
# Source: National List of Essential Medicines India 2022
# ─────────────────────────────────────────────────────────────────────────────

NLEM_MEDICINES = [
    # Analgesics / Antipyretics
    {"nlem_code": "NLEM-001", "drug_name": "Paracetamol",            "generic_name": "Acetaminophen",         "form": "Tablet",    "strength": "500 mg",      "unit": "tablets",  "avg_daily": (15, 40)},
    {"nlem_code": "NLEM-002", "drug_name": "Ibuprofen",              "generic_name": "Ibuprofen",              "form": "Tablet",    "strength": "400 mg",      "unit": "tablets",  "avg_daily": (5,  20)},
    {"nlem_code": "NLEM-003", "drug_name": "Aspirin",                "generic_name": "Acetylsalicylic Acid",  "form": "Tablet",    "strength": "75 mg",       "unit": "tablets",  "avg_daily": (3,  10)},

    # Antibiotics
    {"nlem_code": "NLEM-010", "drug_name": "Amoxicillin",            "generic_name": "Amoxicillin",           "form": "Capsule",   "strength": "500 mg",      "unit": "capsules", "avg_daily": (10, 30)},
    {"nlem_code": "NLEM-011", "drug_name": "Cotrimoxazole",          "generic_name": "Sulfamethoxazole+Trimethoprim","form":"Tablet","strength":"480 mg",   "unit": "tablets",  "avg_daily": (5,  15)},
    {"nlem_code": "NLEM-012", "drug_name": "Metronidazole",          "generic_name": "Metronidazole",         "form": "Tablet",    "strength": "400 mg",      "unit": "tablets",  "avg_daily": (8,  25)},
    {"nlem_code": "NLEM-013", "drug_name": "Ciprofloxacin",          "generic_name": "Ciprofloxacin",         "form": "Tablet",    "strength": "500 mg",      "unit": "tablets",  "avg_daily": (4,  12)},
    {"nlem_code": "NLEM-014", "drug_name": "Doxycycline",            "generic_name": "Doxycycline Hyclate",   "form": "Capsule",   "strength": "100 mg",      "unit": "capsules", "avg_daily": (3,  10)},
    {"nlem_code": "NLEM-015", "drug_name": "Azithromycin",           "generic_name": "Azithromycin",          "form": "Tablet",    "strength": "500 mg",      "unit": "tablets",  "avg_daily": (3,  8) },
    {"nlem_code": "NLEM-016", "drug_name": "Benzylpenicillin",       "generic_name": "Penicillin G",          "form": "Injection", "strength": "10 lac IU",   "unit": "vials",    "avg_daily": (1,  5) },

    # Anti-malarials
    {"nlem_code": "NLEM-020", "drug_name": "Chloroquine Phosphate",  "generic_name": "Chloroquine",           "form": "Tablet",    "strength": "250 mg",      "unit": "tablets",  "avg_daily": (4,  12)},
    {"nlem_code": "NLEM-021", "drug_name": "Artesunate",             "generic_name": "Artesunate",            "form": "Tablet",    "strength": "50 mg",       "unit": "tablets",  "avg_daily": (2,  8) },
    {"nlem_code": "NLEM-022", "drug_name": "Primaquine",             "generic_name": "Primaquine Phosphate",  "form": "Tablet",    "strength": "7.5 mg",      "unit": "tablets",  "avg_daily": (2,  6) },

    # Anti-tuberculosis
    {"nlem_code": "NLEM-030", "drug_name": "Rifampicin",             "generic_name": "Rifampicin",            "form": "Tablet",    "strength": "450 mg",      "unit": "tablets",  "avg_daily": (3,  8) },
    {"nlem_code": "NLEM-031", "drug_name": "Isoniazid",              "generic_name": "Isoniazid",             "form": "Tablet",    "strength": "300 mg",      "unit": "tablets",  "avg_daily": (3,  8) },
    {"nlem_code": "NLEM-032", "drug_name": "Pyrazinamide",           "generic_name": "Pyrazinamide",          "form": "Tablet",    "strength": "500 mg",      "unit": "tablets",  "avg_daily": (3,  8) },

    # Oral Rehydration & Nutrition
    {"nlem_code": "NLEM-040", "drug_name": "ORS Powder",             "generic_name": "Oral Rehydration Salts","form": "Sachet",   "strength": "WHO formula", "unit": "sachets",  "avg_daily": (10, 50)},
    {"nlem_code": "NLEM-041", "drug_name": "Zinc Sulphate",          "generic_name": "Zinc Sulfate",          "form": "Tablet",    "strength": "20 mg",       "unit": "tablets",  "avg_daily": (5,  20)},
    {"nlem_code": "NLEM-042", "drug_name": "Iron Folic Acid",        "generic_name": "Ferrous Sulfate + FA",  "form": "Tablet",    "strength": "100 mg+0.5 mg","unit": "tablets", "avg_daily": (8,  25)},

    # Cardiovascular
    {"nlem_code": "NLEM-050", "drug_name": "Atenolol",               "generic_name": "Atenolol",              "form": "Tablet",    "strength": "50 mg",       "unit": "tablets",  "avg_daily": (3,  10)},
    {"nlem_code": "NLEM-051", "drug_name": "Amlodipine",             "generic_name": "Amlodipine Besylate",   "form": "Tablet",    "strength": "5 mg",        "unit": "tablets",  "avg_daily": (4,  12)},
    {"nlem_code": "NLEM-052", "drug_name": "Enalapril",              "generic_name": "Enalapril Maleate",     "form": "Tablet",    "strength": "5 mg",        "unit": "tablets",  "avg_daily": (3,  10)},

    # Diabetes
    {"nlem_code": "NLEM-060", "drug_name": "Metformin",              "generic_name": "Metformin HCl",         "form": "Tablet",    "strength": "500 mg",      "unit": "tablets",  "avg_daily": (6,  20)},
    {"nlem_code": "NLEM-061", "drug_name": "Glibenclamide",          "generic_name": "Glibenclamide",         "form": "Tablet",    "strength": "5 mg",        "unit": "tablets",  "avg_daily": (3,  10)},

    # Respiratory
    {"nlem_code": "NLEM-070", "drug_name": "Salbutamol Inhaler",     "generic_name": "Albuterol",             "form": "Inhaler",   "strength": "100 mcg/dose","unit": "inhalers", "avg_daily": (0,  2) },
    {"nlem_code": "NLEM-071", "drug_name": "Prednisolone",           "generic_name": "Prednisolone",          "form": "Tablet",    "strength": "5 mg",        "unit": "tablets",  "avg_daily": (3,  10)},

    # Vitamins / Supplements
    {"nlem_code": "NLEM-080", "drug_name": "Vitamin A",              "generic_name": "Retinol",               "form": "Capsule",   "strength": "1 lakh IU",   "unit": "capsules", "avg_daily": (1,  5) },
    {"nlem_code": "NLEM-081", "drug_name": "Vitamin B Complex",      "generic_name": "B1+B2+B6+B12",          "form": "Tablet",    "strength": "Standard",    "unit": "tablets",  "avg_daily": (4,  12)},

    # Vaccines (stored separately; seeded as inventory for stock tracking)
    {"nlem_code": "NLEM-090", "drug_name": "OPV Vaccine",            "generic_name": "Oral Polio Vaccine",    "form": "Vial",      "strength": "10 dose",     "unit": "vials",    "avg_daily": (0,  3) },
    {"nlem_code": "NLEM-091", "drug_name": "BCG Vaccine",            "generic_name": "Bacillus Calmette-Guérin","form":"Vial",    "strength": "10 dose",     "unit": "vials",    "avg_daily": (0,  2) },

    # Antiseptics / Topicals
    {"nlem_code": "NLEM-100", "drug_name": "Povidone Iodine",        "generic_name": "Povidone Iodine",       "form": "Solution",  "strength": "5%",          "unit": "bottles",  "avg_daily": (0,  3) },
]

# Map district → primary vendor code (for auto-assigning orders)
DISTRICT_PRIMARY_VENDOR = {
    "Pune":       "VND-PUN-01",
    "Nashik":     "VND-NSK-01",
    "Aurangabad": "VND-AUR-01",
    "Latur":      "VND-LAT-01",
    "Amravati":   "VND-AMR-01",
}


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _random_batch() -> str:
    prefix = random.choice(["BT", "MH", "NK", "PH"])
    return f"{prefix}{random.randint(10000, 99999)}"


def _random_expiry(months_min: int = 3, months_max: int = 36) -> date:
    today = date.today()
    days = random.randint(months_min * 30, months_max * 30)
    return today + timedelta(days=days)


def _expiry_with_risk() -> date:
    """Occasionally produce an expiring-soon or expired batch for realism."""
    roll = random.random()
    today = date.today()
    if roll < 0.05:    # 5% chance → already expired
        return today - timedelta(days=random.randint(1, 30))
    elif roll < 0.15:  # 10% chance → expiring within 30 days
        return today + timedelta(days=random.randint(1, 29))
    else:
        return _random_expiry()


def _quantity_with_risk(rop: float, avg_daily: float) -> int:
    """
    Produce realistic quantity distribution:
      15% chance → critically low (≤ 3 days stock)
      20% chance → at reorder point (low)
      65% chance → healthy
    """
    roll = random.random()
    if roll < 0.15:
        return max(0, int(avg_daily * random.uniform(0, 3)))
    elif roll < 0.35:
        return max(0, int(rop * random.uniform(0.5, 1.0)))
    else:
        return int(rop * random.uniform(1.5, 5.0))


# ─────────────────────────────────────────────────────────────────────────────
# SEED FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def seed_phcs(db) -> dict:
    """Insert PHC rows, return {phc_code: PHC} map."""
    phc_map = {}
    for p in PHC_MASTER:
        phc = PHC(
            name          = p["name"],
            phc_code      = p["phc_code"],
            district      = p["district"],
            state         = "Maharashtra",
            block         = p["block"],
            village       = p["village"],
            latitude      = p["lat"] + random.uniform(-0.01, 0.01),  # slight jitter
            longitude     = p["lon"] + random.uniform(-0.01, 0.01),
            contact_name  = f"Dr. {random.choice(['Patil','Jadhav','Shinde','Desai','More'])}",
            contact_phone = f"98{random.randint(10000000, 99999999)}",
            language      = p["lang"],
            is_active     = True,
        )
        db.add(phc)
        phc_map[p["phc_code"]] = phc

    db.flush()  # assigns IDs before we need them
    print(f"  ✓ Seeded {len(PHC_MASTER)} PHCs")
    return phc_map


def seed_vendors(db) -> dict:
    """Insert Vendor rows, return {vendor_code: Vendor} map."""
    vendor_map = {}
    for v in VENDOR_MASTER:
        vendor = Vendor(
            name           = v["name"],
            vendor_code    = v["code"],
            district       = v["district"],
            state          = "Maharashtra",
            contact_name   = f"Mr. {random.choice(['Kumar','Singh','Verma','Mehta','Gupta'])}",
            phone          = v["phone"],
            whatsapp       = v["phone"],
            preferred_lang = v["lang"],
            avg_lead_days  = v["lead_days"],
            service_radius_km = random.choice([30.0, 50.0, 75.0]),
            is_active      = True,
        )
        db.add(vendor)
        vendor_map[v["code"]] = vendor

    db.flush()
    print(f"  ✓ Seeded {len(VENDOR_MASTER)} vendors")
    return vendor_map


def seed_inventory(db, phc_map: dict) -> None:
    """Insert InventoryItem rows for every PHC × every NLEM drug."""
    count = 0
    for phc in phc_map.values():
        for drug in NLEM_MEDICINES:
            avg_min, avg_max = drug["avg_daily"]
            avg_daily   = round(random.uniform(avg_min, avg_max), 1)
            lead_days   = random.randint(5, 10)
            safety_days = random.randint(3, 7)

            rop = compute_reorder_point(avg_daily, lead_days, safety_days)
            qty = _quantity_with_risk(rop, avg_daily)
            expiry = _expiry_with_risk()

            status = classify_stock_status(
                quantity_on_hand=qty,
                reorder_point=rop,
                avg_daily_consumption=avg_daily,
                expiry_date=expiry,
            )

            item = InventoryItem(
                phc_id               = phc.id,
                nlem_code            = drug["nlem_code"],
                drug_name            = drug["drug_name"],
                generic_name         = drug["generic_name"],
                dosage_form          = drug["form"],
                strength             = drug["strength"],
                unit                 = drug["unit"],
                batch_no             = _random_batch(),
                quantity_on_hand     = qty,
                expiry_date          = expiry,
                avg_daily_consumption= avg_daily,
                supplier_lead_days   = lead_days,
                safety_stock_days    = safety_days,
                reorder_point        = rop,
                max_stock_level      = int(avg_daily * 60),  # 60-day ceiling
                stock_status         = status,
            )
            db.add(item)
            count += 1

    db.flush()
    print(f"  ✓ Seeded {count} inventory rows ({len(phc_map)} PHCs × {len(NLEM_MEDICINES)} drugs)")


def seed_orders(db, phc_map: dict, vendor_map: dict) -> None:
    """Generate ~200 synthetic orders across all pipeline states."""
    phcs = list(phc_map.values())
    statuses = [
        OrderStatus.REQUISITION_SENT,
        OrderStatus.VENDOR_CONFIRMED,
        OrderStatus.IN_TRANSIT,
        OrderStatus.DELIVERED,
        OrderStatus.VERIFIED,
    ]
    status_weights = [0.20, 0.20, 0.25, 0.20, 0.15]

    count = 0
    for _ in range(200):
        phc    = random.choice(phcs)
        drug   = random.choice(NLEM_MEDICINES)
        status = random.choices(statuses, weights=status_weights, k=1)[0]

        vendor_code = DISTRICT_PRIMARY_VENDOR.get(phc.district)
        vendor = vendor_map.get(vendor_code) if vendor_code else None

        today = date.today()
        created_offset = random.randint(0, 30)   # order placed 0-30 days ago
        lead_days      = random.randint(5, 10)
        exp_delivery   = today - timedelta(days=created_offset) + timedelta(days=lead_days)

        qty_ordered = random.randint(50, 500)
        qty_delivered = (
            random.randint(int(qty_ordered * 0.8), qty_ordered)
            if status in (OrderStatus.DELIVERED, OrderStatus.VERIFIED)
            else None
        )
        actual_delivery = (
            exp_delivery + timedelta(days=random.randint(-2, 3))
            if status in (OrderStatus.DELIVERED, OrderStatus.VERIFIED)
            else None
        )

        order = Order(
            phc_id                 = phc.id,
            vendor_id              = vendor.id if vendor else None,
            order_type             = OrderType.VENDOR_ORDER,
            status                 = status,
            nlem_code              = drug["nlem_code"],
            drug_name              = drug["drug_name"],
            quantity_ordered       = qty_ordered,
            quantity_delivered     = qty_delivered,
            expected_delivery_date = exp_delivery,
            actual_delivery_date   = actual_delivery,
            is_auto_generated      = random.choice([True, False]),
            sms_sent               = status != OrderStatus.DRAFT,
            sms_language           = phc.language,
        )
        db.add(order)
        count += 1

    # Add a handful of inter-PHC transfer orders
    for _ in range(20):
        source = random.choice(phcs)
        target = random.choice([p for p in phcs if p.id != source.id])
        drug   = random.choice(NLEM_MEDICINES)

        order = Order(
            phc_id          = target.id,
            source_phc_id   = source.id,
            order_type      = OrderType.INTER_PHC,
            status          = random.choice([OrderStatus.REQUISITION_SENT, OrderStatus.IN_TRANSIT, OrderStatus.DELIVERED]),
            nlem_code       = drug["nlem_code"],
            drug_name       = drug["drug_name"],
            quantity_ordered= random.randint(20, 150),
            is_auto_generated = True,
            sms_sent        = True,
            sms_language    = target.language,
        )
        db.add(order)
        count += 1

    db.flush()
    print(f"  ✓ Seeded {count} orders")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main(reset: bool = False) -> None:
    print("\n══ PHC Supply Chain — Database Seeder ══")

    # Create tables if they don't exist
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        if reset:
            print("  ⚠  --reset: dropping all rows …")
            db.query(Order).delete()
            db.query(InventoryItem).delete()
            db.query(Vendor).delete()
            db.query(PHC).delete()
            db.commit()
            print("  ✓ Tables cleared")

        # Guard against double-seeding
        if db.query(PHC).count() > 0 and not reset:
            print("  ℹ  Database already seeded. Use --reset to reseed.")
            return

        print("\n  Seeding …")
        phc_map    = seed_phcs(db)
        vendor_map = seed_vendors(db)
        seed_inventory(db, phc_map)
        seed_orders(db, phc_map, vendor_map)

        db.commit()
        print(f"\n  ✓ Seed complete.")
        print(f"    PHCs      : {db.query(PHC).count()}")
        print(f"    Vendors   : {db.query(Vendor).count()}")
        print(f"    Inventory : {db.query(InventoryItem).count()}")
        print(f"    Orders    : {db.query(Order).count()}")
        print("══════════════════════════════════════\n")

    except Exception as exc:
        db.rollback()
        print(f"\n  ✗ Seeding failed: {exc}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed the PHC database with synthetic data.")
    parser.add_argument("--reset", action="store_true", help="Wipe existing data before seeding")
    args = parser.parse_args()
    main(reset=args.reset)
