"""
Bed model.
Tracks individual bed occupancy per PHC ward.
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.core.database import Base


class WardType(str, enum.Enum):
    GENERAL    = "general"
    MATERNITY  = "maternity"
    EMERGENCY  = "emergency"


class Bed(Base):
    __tablename__ = "beds"

    id          = Column(Integer, primary_key=True, index=True)
    phc_id      = Column(Integer, ForeignKey("phcs.id", ondelete="CASCADE"), nullable=False, index=True)

    bed_number    = Column(Integer,     nullable=False)          # 1-based within ward
    ward_type     = Column(String(50),  nullable=False, default=WardType.GENERAL)
    is_occupied   = Column(Boolean,     nullable=False, default=False)
    patient_label = Column(String(100), nullable=True)           # e.g. "Male, 34" — optional
    notes         = Column(Text,        nullable=True)

    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationship
    phc = relationship("PHC", backref="beds")

    def __repr__(self):
        return (
            f"<Bed phc_id={self.phc_id} ward={self.ward_type} "
            f"bed={self.bed_number} occupied={self.is_occupied}>"
        )
