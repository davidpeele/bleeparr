from sqlalchemy.orm import Session
from db.models import MonitoredShow
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from db.models import Base

DATABASE_URL = "sqlite:///./bleeparr.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)

def get_monitored_shows():
    db = SessionLocal()
    shows = db.query(MonitoredShow).all()
    db.close()
    return shows

def upsert_monitored_show(tvdb_id: int, title: str, monitored: bool = True):
    db = SessionLocal()
    show = db.query(MonitoredShow).filter(MonitoredShow.tvdb_id == tvdb_id).first()
    if show:
        show.monitored = monitored
    else:
        show = MonitoredShow(tvdb_id=tvdb_id, title=title, monitored=monitored)
        db.add(show)
    db.commit()
    db.close()
