from sqlalchemy import Column, Integer, String, Boolean
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class MonitoredShow(Base):
    __tablename__ = "monitored_shows"
    id = Column(Integer, primary_key=True, index=True)
    tvdb_id = Column(Integer, unique=True, index=True)
    title = Column(String, index=True)
    monitored = Column(Boolean, default=True)
