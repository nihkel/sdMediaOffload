from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SDOFFLOAD_", env_file=".env", extra="ignore")

    db_path: Path = Path("./data/sdoffload.db")
    destination_root: Path = Path("/mnt/media")
    default_template: str = "{camera_slug}/{captured:%Y}/{captured:%Y-%m-%d}/{original_name}"
    host_token: str = "change-me"
    log_level: str = "INFO"
    # Read source files from this prefix when the host reports a mount path.
    # If host and VM see the same path (NFS at same mountpoint), leave empty.
    source_path_remap: str = ""

    @property
    def db_url(self) -> str:
        return f"sqlite:///{self.db_path.resolve()}"


settings = Settings()
