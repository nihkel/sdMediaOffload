from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session

from .config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(
    settings.db_url,
    connect_args={"check_same_thread": False},
    future=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


def init_db() -> None:
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    from . import models  # noqa: F401  -- register tables
    Base.metadata.create_all(bind=engine)
    _seed_default_profiles()


@contextmanager
def session_scope():
    s: Session = SessionLocal()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def get_session():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


def _seed_default_profiles() -> None:
    from . import models
    from .services.camera_detect import DEFAULT_PROFILES

    with session_scope() as s:
        existing = {p.slug for p in s.query(models.CameraProfile).all()}
        for p in DEFAULT_PROFILES:
            if p["slug"] in existing:
                continue
            s.add(models.CameraProfile(
                slug=p["slug"],
                name=p["name"],
                detection_rules=p["detection_rules"],
                dest_template=p["dest_template"],
            ))
