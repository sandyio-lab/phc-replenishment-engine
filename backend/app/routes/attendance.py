"""Daily PHC staff check-in, check-out, and network attendance summary."""

from datetime import date, datetime
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.phc import PHC
from app.models.staff import AttendanceRecord, StaffMember

router = APIRouter(prefix="/attendance", tags=["Attendance"])
INDIA_TIME = ZoneInfo("Asia/Kolkata")


def _today() -> date:
    return datetime.now(INDIA_TIME).date()


def _get_phc_or_404(phc_id: int, db: Session) -> PHC:
    phc = db.query(PHC).filter(
        PHC.id == phc_id,
        PHC.is_active == True,
    ).first()
    if not phc:
        raise HTTPException(status_code=404, detail="Active PHC not found.")
    return phc


def _staff_status(record: Optional[AttendanceRecord]) -> str:
    if not record:
        return "not_checked_in"
    return "checked_out" if record.check_out_at else "on_duty"


def _india_isoformat(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=INDIA_TIME)
    return value.astimezone(INDIA_TIME).isoformat()


def _staff_payload(staff: StaffMember, record: Optional[AttendanceRecord]) -> dict:
    return {
        "staff_id": staff.id,
        "staff_code": staff.staff_code,
        "full_name": staff.full_name,
        "designation": staff.designation,
        "status": _staff_status(record),
        "check_in_at": _india_isoformat(record.check_in_at) if record else None,
        "check_out_at": _india_isoformat(record.check_out_at) if record and record.check_out_at else None,
    }


@router.get("/phcs/{phc_id}/today")
def get_phc_attendance_today(phc_id: int, db: Session = Depends(get_db)):
    phc = _get_phc_or_404(phc_id, db)
    staff = db.query(StaffMember).filter(
        StaffMember.phc_id == phc.id,
        StaffMember.is_active == True,
    ).order_by(StaffMember.designation, StaffMember.full_name).all()
    records = db.query(AttendanceRecord).filter(
        AttendanceRecord.work_date == _today(),
        AttendanceRecord.staff_id.in_([member.id for member in staff]),
    ).all() if staff else []
    record_by_staff = {record.staff_id: record for record in records}
    members = [_staff_payload(member, record_by_staff.get(member.id)) for member in staff]
    checked_in = sum(member["status"] != "not_checked_in" for member in members)
    checked_out = sum(member["status"] == "checked_out" for member in members)
    return {
        "phc_id": phc.id,
        "phc_name": phc.name,
        "work_date": _today().isoformat(),
        "total_staff": len(members),
        "checked_in": checked_in,
        "on_duty": checked_in - checked_out,
        "checked_out": checked_out,
        "not_checked_in": len(members) - checked_in,
        "staff": members,
    }


@router.post("/staff/{staff_id}/check-in", status_code=201)
def check_in(staff_id: int, db: Session = Depends(get_db)):
    staff = db.query(StaffMember).join(PHC, PHC.id == StaffMember.phc_id).filter(
        StaffMember.id == staff_id,
        StaffMember.is_active == True,
    ).first()
    if not staff:
        raise HTTPException(status_code=404, detail="Active staff member not found.")

    today = _today()
    existing = db.query(AttendanceRecord).filter(
        AttendanceRecord.staff_id == staff.id,
        AttendanceRecord.work_date == today,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Attendance is already recorded for today.")

    record = AttendanceRecord(
        staff_id=staff.id,
        work_date=today,
        check_in_at=datetime.now(INDIA_TIME),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return _staff_payload(staff, record)


@router.post("/staff/{staff_id}/check-out")
def check_out(staff_id: int, db: Session = Depends(get_db)):
    staff = db.query(StaffMember).join(PHC, PHC.id == StaffMember.phc_id).filter(
        StaffMember.id == staff_id,
        StaffMember.is_active == True,
    ).first()
    if not staff:
        raise HTTPException(status_code=404, detail="Active staff member not found.")

    record = db.query(AttendanceRecord).filter(
        AttendanceRecord.staff_id == staff.id,
        AttendanceRecord.work_date == _today(),
    ).first()
    if not record:
        raise HTTPException(status_code=409, detail="Check in before checking out.")
    if record.check_out_at:
        raise HTTPException(status_code=409, detail="Attendance is already checked out for today.")

    record.check_out_at = datetime.now(INDIA_TIME)
    db.commit()
    db.refresh(record)
    return _staff_payload(staff, record)


@router.get("/network/today")
def get_network_attendance_today(db: Session = Depends(get_db)):
    work_date = _today()
    phcs = db.query(PHC).filter(PHC.is_active == True).order_by(PHC.district, PHC.name).all()
    phc_ids = [phc.id for phc in phcs]
    staff = db.query(StaffMember).filter(
        StaffMember.phc_id.in_(phc_ids),
        StaffMember.is_active == True,
    ).order_by(StaffMember.full_name).all() if phc_ids else []
    records = db.query(AttendanceRecord).filter(
        AttendanceRecord.work_date == work_date,
        AttendanceRecord.staff_id.in_([member.id for member in staff]),
    ).all() if staff else []
    record_by_staff = {record.staff_id: record for record in records}
    staff_by_phc: dict[int, list[dict]] = {phc.id: [] for phc in phcs}
    for member in staff:
        staff_by_phc[member.phc_id].append(_staff_payload(member, record_by_staff.get(member.id)))

    results = []
    for phc in phcs:
        members = staff_by_phc[phc.id]
        checked_in = sum(member["status"] != "not_checked_in" for member in members)
        checked_out = sum(member["status"] == "checked_out" for member in members)
        results.append({
            "phc_id": phc.id,
            "phc_code": phc.phc_code,
            "phc_name": phc.name,
            "district": phc.district,
            "total_staff": len(members),
            "checked_in": checked_in,
            "on_duty": checked_in - checked_out,
            "checked_out": checked_out,
            "not_checked_in": len(members) - checked_in,
            "staff": members,
        })

    totals = {
        "phcs": len(results),
        "staff": sum(item["total_staff"] for item in results),
        "checked_in": sum(item["checked_in"] for item in results),
        "on_duty": sum(item["on_duty"] for item in results),
        "checked_out": sum(item["checked_out"] for item in results),
        "not_checked_in": sum(item["not_checked_in"] for item in results),
    }
    return {"work_date": work_date.isoformat(), "totals": totals, "phcs": results}