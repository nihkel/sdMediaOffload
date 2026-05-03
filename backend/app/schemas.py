from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class HostDeviceAttached(BaseModel):
    fs_uuid: Optional[str] = None
    serial: Optional[str] = None
    label: Optional[str] = None
    fs_type: Optional[str] = None
    size_bytes: Optional[int] = None
    mount_path: str


class HostDeviceDetached(BaseModel):
    fs_uuid: Optional[str] = None
    serial: Optional[str] = None
    mount_path: str


class CameraProfileOut(BaseModel):
    id: int
    slug: str
    name: str
    detection_rules: dict
    dest_template: str

    class Config:
        from_attributes = True


class DeviceOut(BaseModel):
    id: int
    fs_uuid: Optional[str]
    serial: Optional[str]
    label: Optional[str]
    fs_type: Optional[str]
    size_bytes: Optional[int]
    detected_camera: Optional[CameraProfileOut] = None
    first_seen: datetime
    last_seen: datetime

    class Config:
        from_attributes = True


class ImportOut(BaseModel):
    id: int
    device_id: int
    camera_profile_id: Optional[int]
    mount_path: str
    status: str
    files_total: int
    files_new: int
    files_skipped: int
    files_failed: int
    bytes_total: int
    bytes_copied: int
    started_at: datetime
    finished_at: Optional[datetime]
    error: Optional[str]
    device: Optional[DeviceOut] = None
    camera_profile: Optional[CameraProfileOut] = None

    class Config:
        from_attributes = True


class MediaFileOut(BaseModel):
    id: int
    original_name: str
    size_bytes: int
    mime_type: Optional[str]
    exif_make: Optional[str]
    exif_model: Optional[str]
    captured_at: Optional[datetime]
    duration_seconds: Optional[float]
    width: Optional[int]
    height: Optional[int]
    dest_path: str
    imported_at: datetime

    class Config:
        from_attributes = True


class EventOut(BaseModel):
    id: int
    ts: datetime
    level: str
    source: str
    message: str
    import_id: Optional[int]
    device_id: Optional[int]
    data: Optional[dict]

    class Config:
        from_attributes = True


class CameraProfileUpsert(BaseModel):
    slug: str = Field(min_length=1, max_length=64)
    name: str
    detection_rules: dict
    dest_template: str
