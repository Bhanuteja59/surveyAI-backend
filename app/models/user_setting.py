from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.core.database import Base


class UserSetting(Base):
    __tablename__ = "user_settings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    theme = Column(String(20), default="light")
    notifications_enabled = Column(Boolean, default=True)
    preferences = Column(JSON, nullable=True)

    user = relationship("User", backref="settings")
