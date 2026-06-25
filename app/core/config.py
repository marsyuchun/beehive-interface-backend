from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "API Pilot"
    database_url: str = "sqlite:///./api_pilot.db"
    demo_base_url: str = "http://127.0.0.1:5000"
    reports_dir: Path = Path("reports/platform")
    run_event_dir: Path = Path("logs/runs")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
