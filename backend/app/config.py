from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SDOFFLOAD_", env_file=".env", extra="ignore")

    db_path: Path = Path("./data/sdoffload.db")
    thumbs_dir: Path = Path("./data/thumbs")
    destination_root: Path = Path("/mnt/media")
    default_template: str = "{camera_slug}/{captured:%Y}/{captured:%Y-%m-%d}/{original_name}"
    host_token: str = "change-me"
    log_level: str = "INFO"
    # Read source files from this prefix when the host reports a mount path.
    # If host and VM see the same path (NFS at same mountpoint), leave empty.
    source_path_remap: str = ""
    # URL of the host-agent's HTTP server (e.g. http://10.0.10.30:8901).
    # Required for eject-from-UI; if empty, eject button is disabled.
    host_agent_url: str = ""
    # Refuse to start an import if free destination space is < bytes_total + this safety buffer.
    space_safety_bytes: int = 1024 * 1024 * 1024  # 1 GiB
    # Webhook (ntfy.sh-compatible) called on terminal import status changes.
    # Examples:
    #   https://ntfy.sh/your-private-topic
    #   https://discord.com/api/webhooks/...    (still posts text body, may need format)
    notify_url: str = ""

    @property
    def db_url(self) -> str:
        return f"sqlite:///{self.db_path.resolve()}"


settings = Settings()
