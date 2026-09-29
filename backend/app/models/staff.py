"""PHC staff roster and daily attendance records."""

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.core.database import Base


class StaffMember(Base):
    __tablename__ = "staff_members"
    __table_args__ = (UniqueConstraint("phc_id", "staff_code", name="uq_staff_phc_code"),)

    id = Column(Integer, primary_key=True, index=True)
    phc_id = Column(Integer, ForeignKey("phcs.id", ondelete="CASCADE"), nullable=False, index=True)
    staff_code = Column(String(50), nullable=False)
    full_name = Column(String(150), nullable=False)
    designation = Column(String(100), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)

    phc = relationship("PHC")
    attendance_records = relationship("AttendanceRecord", back_populates="staff", cascade="all, delete-orphan")


class AttendanceRecord(Base):
    __tablename__ = "attendance_records"
    __table_args__ = (UniqueConstraint("staff_id", "work_date", name="uq_attendance_staff_day"),)

    id = Column(Integer, primary_key=True, index=True)
    staff_id = Column(Integer, ForeignKey("staff_members.id", ondelete="CASCADE"), nullable=False, index=True)
    work_date = Column(Date, nullable=False, index=True)
    check_in_at = Column(DateTime(timezone=True), nullable=False)
    check_out_at = Column(DateTime(timezone=True), nullable=True)

    staff = relationship("StaffMember", back_populates="attendance_records")