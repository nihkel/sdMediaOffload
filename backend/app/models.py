from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, DateTime, ForeignKey, Text, JSON, BigInteger, Float, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class CameraProfile(Base):
    __tablename__ = "camera_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(128))
    detection_rules: Mapped[dict] = mapped_column(JSON)
    dest_template: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(primary_key=True)
    fs_uuid: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    serial: Mapped[Optional[str]] = mapped_column(String(128), index=True)
    label: Mapped[Optional[str]] = mapped_column(String(128))
    fs_type: Mapped[Optional[str]] = mapped_column(String(32))
    size_bytes: Mapped[Optional[int]] = mapped_column(BigInteger)
    detected_camera_id: Mapped[Optional[int]] = mapped_column(ForeignKey("camera_profiles.id"))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    first_seen: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_seen: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    detected_camera: Mapped[Optional["CameraProfile"]] = relationship(lazy="joined")

    __table_args__ = (
        UniqueConstraint("fs_uuid", "serial", name="uq_device_identity"),
    )


class Import(Base):
    __tablename__ = "imports"

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), index=True)
    camera_profile_id: Mapped[Optional[int]] = mapped_column(ForeignKey("camera_profiles.id"))
    mount_path: Mapped[str] = mapped_column(String(512))
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    files_total: Mapped[int] = mapped_column(Integer, default=0)
    files_new: Mapped[int] = mapped_column(Integer, default=0)
    files_skipped: Mapped[int] = mapped_column(Integer, default=0)
    files_failed: Mapped[int] = mapped_column(Integer, default=0)
    bytes_total: Mapped[int] = mapped_column(BigInteger, default=0)
    bytes_copied: Mapped[int] = mapped_column(BigInteger, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    error: Mapped[Optional[str]] = mapped_column(Text)

    device: Mapped["Device"] = relationship(lazy="joined")
    camera_profile: Mapped[Optional["CameraProfile"]] = relationship(lazy="joined")


class MediaFile(Base):
    __tablename__ = "media_files"

    id: Mapped[int] = mapped_column(primary_key=True)
    partial_hash: Mapped[str] = mapped_column(String(64), index=True)
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    original_name: Mapped[str] = mapped_column(String(255))
    full_hash: Mapped[Optional[str]] = mapped_column(String(64))
    mime_type: Mapped[Optional[str]] = mapped_column(String(64))
    exif_make: Mapped[Optional[str]] = mapped_column(String(64))
    exif_model: Mapped[Optional[str]] = mapped_column(String(128))
    captured_at: Mapped[Optional[datetime]] = mapped_column(DateTime, index=True)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float)
    width: Mapped[Optional[int]] = mapped_column(Integer)
    height: Mapped[Optional[int]] = mapped_column(Integer)
    dest_path: Mapped[str] = mapped_column(String(1024))
    original_path_on_device: Mapped[str] = mapped_column(String(1024))
    first_import_id: Mapped[int] = mapped_column(ForeignKey("imports.id"))
    first_device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"))
    imported_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    first_import: Mapped["Import"] = relationship(foreign_keys=[first_import_id])
    first_device: Mapped["Device"] = relationship(foreign_keys=[first_device_id])

    __table_args__ = (
        UniqueConstraint("partial_hash", "size_bytes", "original_name", name="uq_media_dedup"),
        Index("idx_media_captured", "captured_at"),
    )


class ImportSkip(Base):
    __tablename__ = "import_skips"

    id: Mapped[int] = mapped_column(primary_key=True)
    import_id: Mapped[int] = mapped_column(ForeignKey("imports.id"), index=True)
    original_path: Mapped[str] = mapped_column(String(1024))
    reason: Mapped[str] = mapped_column(String(64))
    matched_media_id: Mapped[Optional[int]] = mapped_column(ForeignKey("media_files.id"))
    detail: Mapped[Optional[str]] = mapped_column(Text)


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    level: Mapped[str] = mapped_column(String(16), default="info")
    source: Mapped[str] = mapped_column(String(32))
    import_id: Mapped[Optional[int]] = mapped_column(ForeignKey("imports.id"), index=True)
    device_id: Mapped[Optional[int]] = mapped_column(ForeignKey("devices.id"))
    message: Mapped[str] = mapped_column(Text)
    data: Mapped[Optional[dict]] = mapped_column(JSON)


class AppSetting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
