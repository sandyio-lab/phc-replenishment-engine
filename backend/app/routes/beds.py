"""
Bed Routes
GET  /beds/{phc_id}          — all beds for a PHC, grouped by ward
PATCH /beds/{bed_id}         — toggle occupied / update patient label
POST /beds/seed/{phc_id}     — auto-create default ward beds for a PHC (idempotent)
GET  /beds/summary/{phc_id}  — quick occupancy counts per ward
"""

from typing import List, Optional
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.bed    import Bed, WardType
from app.models.phc    import PHC

router = APIRouter(prefix="/beds", tags=["Beds"])

# Default ward layout seeded for every PHC
_DEFAULT_WARDS: List[dict] = [
    {"ward_type": WardType.GENERAL,   "count": 10},
    {"ward_type": WardType.MATERNITY, "count": 4},
    {"ward_type": WardType.EMERGENCY, "count": 2},
]


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class BedRead(BaseModel):
    id:            int
    phc_id:        int
    bed_number:    int
    ward_type:     str
    is_occupied:   bool
    patient_label: Optional[str] = None
    updated_at:    Optional[datetime] = None

    class Config:
        from_attributes = True


class BedUpdate(BaseModel):
    is_occupied:   bool
    patient_label: Optional[str] = None


class WardSummary(BaseModel):
    ward_type:    str
    total:        int
    occupied:     int
    available:    int
    beds:         List[BedRead]


class PhcBedSummary(BaseModel):
    phc_id:         int
    total_beds:     int
    occupied_beds:  int
    available_beds: int
    wards:          List[WardSummary]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_phc_or_404(phc_id: int, db: Session) -> PHC:
    phc = db.query(PHC).filter(PHC.id == phc_id).first()
    if not phc:
        raise HTTPException(status_code=404, detail="PHC not found.")
    return phc


def _group_by_ward(beds: List[Bed]) -> List[WardSummary]:
    ward_order = [WardType.GENERAL, WardType.MATERNITY, WardType.EMERGENCY]
    grouped: dict[str, List[Bed]] = {}
    for b in beds:
        grouped.setdefault(b.ward_type, []).append(b)

    result = []
    for wt in ward_order:
        wt_val = wt.value if hasattr(wt, "value") else wt
        ward_beds = sorted(grouped.get(wt_val, []), key=lambda x: x.bed_number)
        occupied = sum(1 for b in ward_beds if b.is_occupied)
        result.append(WardSummary(
            ward_type=wt_val,
            total=len(ward_beds),
            occupied=occupied,
            available=len(ward_beds) - occupied,
            beds=[BedRead.model_validate(b) for b in ward_beds],
        ))
    # Include any custom wards not in the default order
    for wt_val, ward_beds in grouped.items():
        if wt_val not in [w.value for w in ward_order]:
            occupied = sum(1 for b in ward_beds if b.is_occupied)
            result.append(WardSummary(
                ward_type=wt_val,
                total=len(ward_beds),
                occupied=occupied,
                available=len(ward_beds) - occupied,
                beds=[BedRead.model_validate(b) for b in sorted(ward_beds, key=lambda x: x.bed_number)],
            ))
    return result


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/seed/{phc_id}", tags=["Beds"])
def seed_beds(phc_id: int, db: Session = Depends(get_db)):
    """
    Idempotent — creates default beds for a PHC only if none exist yet.
    Safe to call multiple times.
    """
    _get_phc_or_404(phc_id, db)
    existing = db.query(Bed).filter(Bed.phc_id == phc_id).count()
    if existing > 0:
        return {"message": f"Beds already seeded for PHC {phc_id}.", "created": 0}

    created = 0
    for ward in _DEFAULT_WARDS:
        for n in range(1, ward["count"] + 1):
            db.add(Bed(
                phc_id      = phc_id,
                ward_type   = ward["ward_type"].value,
                bed_number  = n,
                is_occupied = False,
            ))
            created += 1

    db.commit()
    return {"message": f"Seeded {created} beds for PHC {phc_id}.", "created": created}


@router.get("/summary/{phc_id}", response_model=PhcBedSummary)
def get_bed_summary(phc_id: int, db: Session = Depends(get_db)):
    """Quick occupancy summary for a PHC — used by dashboard detail card."""
    _get_phc_or_404(phc_id, db)
    beds = db.query(Bed).filter(Bed.phc_id == phc_id).all()
    occupied = sum(1 for b in beds if b.is_occupied)
    return PhcBedSummary(
        phc_id         = phc_id,
        total_beds     = len(beds),
        occupied_beds  = occupied,
        available_beds = len(beds) - occupied,
        wards          = _group_by_ward(beds),
    )


@router.get("/{phc_id}", response_model=PhcBedSummary)
def get_phc_beds(phc_id: int, db: Session = Depends(get_db)):
    """Full bed list for a PHC, grouped by ward. Used by the worker ward modal."""
    _get_phc_or_404(phc_id, db)
    beds = db.query(Bed).filter(Bed.phc_id == phc_id).order_by(Bed.ward_type, Bed.bed_number).all()

    # Auto-seed if this PHC has no beds yet (first time a worker opens the ward view)
    if not beds:
        for ward in _DEFAULT_WARDS:
            for n in range(1, ward["count"] + 1):
                b = Bed(
                    phc_id      = phc_id,
                    ward_type   = ward["ward_type"].value,
                    bed_number  = n,
                    is_occupied = False,
                )
                db.add(b)
                beds.append(b)
        db.commit()
        for b in beds:
            db.refresh(b)

    occupied = sum(1 for b in beds if b.is_occupied)
    return PhcBedSummary(
        phc_id         = phc_id,
        total_beds     = len(beds),
        occupied_beds  = occupied,
        available_beds = len(beds) - occupied,
        wards          = _group_by_ward(beds),
    )


@router.patch("/{bed_id}", response_model=BedRead)
def update_bed(bed_id: int, payload: BedUpdate, db: Session = Depends(get_db)):
    """Toggle a bed's occupied state and optionally set a patient label."""
    bed = (
        db.query(Bed)
        .join(PHC, PHC.id == Bed.phc_id)
        .filter(Bed.id == bed_id)
        .first()
    )
    if not bed:
        raise HTTPException(status_code=404, detail="Bed not found.")

    bed.is_occupied   = payload.is_occupied
    bed.patient_label = payload.patient_label if payload.is_occupied else None
    db.commit()
    db.refresh(bed)
    return bed
