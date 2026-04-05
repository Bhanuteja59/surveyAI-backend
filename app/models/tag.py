from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Table
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


# Association Table for Many-to-Many Relationship between Survey and Tag
survey_tag_association = Table(
    "survey_tag",
    Base.metadata,
    Column("survey_id", Integer, ForeignKey("surveys.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    name = Column(String(50), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    surveys = relationship("Survey", secondary=survey_tag_association, back_populates="tags")
    tenant = relationship("Tenant")
