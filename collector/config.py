import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


@dataclass
class OrchestratorConfig:
    """
    Supports both UiPath Automation Cloud and On-Premises Orchestrator.
    Set UIPATH_MODE=cloud or UIPATH_MODE=onprem in your .env file.
    """
    mode: str

    # Cloud credentials
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    organization: Optional[str] = None
    tenant: Optional[str] = None

    # On-prem credentials
    base_url: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    tenancy_name: Optional[str] = None

    # Common
    folder_id: Optional[str] = None

    @classmethod
    def from_env(cls):
        mode = os.getenv("UIPATH_MODE", "cloud").lower()
        if mode == "cloud":
            return cls(
                mode="cloud",
                client_id=os.environ["UIPATH_CLIENT_ID"],
                client_secret=os.environ["UIPATH_CLIENT_SECRET"],
                organization=os.environ["UIPATH_ORGANIZATION"],
                tenant=os.environ["UIPATH_TENANT"],
                folder_id=os.getenv("UIPATH_FOLDER_ID"),
            )
        else:
            return cls(
                mode="onprem",
                base_url=os.environ["UIPATH_BASE_URL"].rstrip("/"),
                username=os.environ["UIPATH_USERNAME"],
                password=os.environ["UIPATH_PASSWORD"],
                tenancy_name=os.getenv("UIPATH_TENANCY_NAME", "Default"),
                folder_id=os.getenv("UIPATH_FOLDER_ID"),
            )

    @property
    def api_base(self) -> str:
        if self.mode == "cloud":
            return f"https://cloud.uipath.com/{self.organization}/{self.tenant}/orchestrator_/odata"
        return f"{self.base_url}/odata"


@dataclass
class AppSignalConfig:
    push_api_key: str
    app_name: str = "RPAWatch"

    @classmethod
    def from_env(cls):
        return cls(
            push_api_key=os.environ["APPSIGNAL_PUSH_API_KEY"],
            app_name=os.getenv("APPSIGNAL_APP_NAME", "RPAWatch"),
        )


@dataclass
class CollectorConfig:
    poll_interval_seconds: int = 60
    lookback_minutes: int = 5

    @classmethod
    def from_env(cls):
        return cls(
            poll_interval_seconds=int(os.getenv("POLL_INTERVAL_SECONDS", "60")),
            lookback_minutes=int(os.getenv("LOOKBACK_MINUTES", "5")),
        )
