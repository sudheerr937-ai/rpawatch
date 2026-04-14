import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import requests

from .config import OrchestratorConfig

logger = logging.getLogger(__name__)

CLOUD_AUTH_URL = "https://account.uipath.com/oauth/token"


class AuthenticationError(Exception):
    pass


class OrchestratorClient:
    """
    Unified client for UiPath Orchestrator — works with both
    Automation Cloud (OAuth2 client credentials) and On-Premises
    (username/password bearer token).
    """

    def __init__(self, config: OrchestratorConfig):
        self.config = config
        self.session = requests.Session()
        self._token: str | None = None
        self._token_expiry: float = 0

    # ------------------------------------------------------------------ #
    #  Authentication                                                       #
    # ------------------------------------------------------------------ #

    def _ensure_authenticated(self):
        """Re-authenticates if token is missing or within 60s of expiry."""
        if self._token and time.time() < self._token_expiry - 60:
            return
        if self.config.mode == "cloud":
            self._auth_cloud()
        else:
            self._auth_onprem()

    def _auth_cloud(self):
        """OAuth2 client credentials flow for UiPath Automation Cloud."""
        resp = requests.post(
            CLOUD_AUTH_URL,
            json={
                "grant_type": "client_credentials",
                "client_id": self.config.client_id,
                "client_secret": self.config.client_secret,
                "audience": "https://orchestrator.cloud.uipath.com",
            },
            timeout=15,
        )
        if not resp.ok:
            raise AuthenticationError(
                f"Cloud auth failed [{resp.status_code}]: {resp.text}"
            )
        data = resp.json()
        self._token = data["access_token"]
        self._token_expiry = time.time() + data.get("expires_in", 3600)
        self._set_auth_headers()
        logger.info("Authenticated with UiPath Automation Cloud.")

    def _auth_onprem(self):
        """Username/password authentication for On-Premises Orchestrator."""
        resp = requests.post(
            f"{self.config.base_url}/api/account/authenticate",
            json={
                "tenancyName": self.config.tenancy_name,
                "usernameOrEmailAddress": self.config.username,
                "password": self.config.password,
            },
            timeout=15,
        )
        if not resp.ok:
            raise AuthenticationError(
                f"On-prem auth failed [{resp.status_code}]: {resp.text}"
            )
        self._token = resp.json()["result"]
        # On-prem tokens typically last 30 minutes
        self._token_expiry = time.time() + 1800
        self._set_auth_headers()
        logger.info("Authenticated with On-Premises Orchestrator.")

    def _set_auth_headers(self):
        self.session.headers.update({"Authorization": f"Bearer {self._token}"})
        if self.config.folder_id:
            self.session.headers["X-UIPATH-OrganizationUnitId"] = self.config.folder_id

    # ------------------------------------------------------------------ #
    #  API helpers                                                          #
    # ------------------------------------------------------------------ #

    def _get(self, path: str, params: dict | None = None) -> dict:
        self._ensure_authenticated()
        url = f"{self.config.api_base}/{path.lstrip('/')}"
        resp = self.session.get(url, params=params, timeout=20)
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------ #
    #  Jobs                                                                 #
    # ------------------------------------------------------------------ #

    def get_jobs_summary(self, lookback_minutes: int = 5) -> list[dict[str, Any]]:
        """
        Returns job counts grouped by (process_name, state) for the
        lookback window. Used to compute faulted rates per process.
        """
        since = (
            datetime.now(timezone.utc) - timedelta(minutes=lookback_minutes)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")

        data = self._get(
            "Jobs",
            params={
                "$filter": f"CreationTime gt {since}",
                "$select": "State,ReleaseName,StartTime,EndTime,HostMachineName",
                "$top": 500,
            },
        )
        return data.get("value", [])

    # ------------------------------------------------------------------ #
    #  Queues                                                               #
    # ------------------------------------------------------------------ #

    def get_queue_definitions(self) -> list[dict[str, Any]]:
        data = self._get("QueueDefinitions", params={"$select": "Id,Name"})
        return data.get("value", [])

    def get_queue_items_summary(self) -> list[dict[str, Any]]:
        """
        Returns all non-processed queue items to measure pending depth
        and failure counts per queue.
        """
        data = self._get(
            "QueueItems",
            params={
                "$filter": "Status eq 'New' or Status eq 'InProgress' or Status eq 'Failed' or Status eq 'Retried'",
                "$select": "Status,QueueDefinitionId,StartProcessing,EndProcessing",
                "$top": 1000,
            },
        )
        return data.get("value", [])

    # ------------------------------------------------------------------ #
    #  Robots / Sessions                                                    #
    # ------------------------------------------------------------------ #

    def get_robot_sessions(self) -> list[dict[str, Any]]:
        """
        Returns current robot session states. Falls back to /Robots
        if /Sessions is not available (older Orchestrator versions).
        """
        try:
            data = self._get(
                "Sessions",
                params={"$select": "State,RobotName,HostMachineName,IsConnected"},
            )
            return data.get("value", [])
        except requests.HTTPError as e:
            if e.response.status_code == 404:
                logger.warning(
                    "Sessions endpoint not found — falling back to /Robots."
                )
                return self._get_robots_fallback()
            raise

    def _get_robots_fallback(self) -> list[dict[str, Any]]:
        data = self._get(
            "Robots",
            params={"$select": "Name,Status,IsConnected,HostMachineName"},
        )
        # Normalise field names to match Sessions schema
        robots = []
        for r in data.get("value", []):
            robots.append(
                {
                    "RobotName": r.get("Name"),
                    "State": r.get("Status"),
                    "HostMachineName": r.get("HostMachineName"),
                    "IsConnected": r.get("IsConnected", False),
                }
            )
        return robots
