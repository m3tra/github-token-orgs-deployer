#!/usr/bin/env python3
"""
Enterprise Secret Deployment Script

- Pulls secret from Azure Key Vault
- Updates GitHub org-level secret across all orgs in enterprise
- Strict typing
- Defensive coding
- Structured JSON logging
"""

from __future__ import annotations

import base64
import json
import logging
import os
import sys
import time
from dataclasses import dataclass
from typing import Any

import requests
from azure.identity import ClientSecretCredential
from azure.keyvault.secrets import SecretClient
from dotenv import load_dotenv
from nacl import encoding, public

# ----------------------------------------------------------------------
# .env loading (non-fatal if missing)
# ----------------------------------------------------------------------
load_dotenv(override=False)


# ----------------------------------------------------------------------
# Structured Logging
# ----------------------------------------------------------------------
class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_record = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
        }
        return json.dumps(log_record)


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logging.basicConfig(level=level.upper(), handlers=[handler])


# ----------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class Config:
    azure_client_id: str
    azure_client_secret: str
    azure_tenant_id: str
    keyvault_name: str
    keyvault_secret_name: str
    github_token: str
    github_enterprise: str
    request_timeout: int
    max_retries: int


def load_config() -> Config:
    required_vars = [
        "AZURE_CLIENT_ID",
        "AZURE_CLIENT_SECRET",
        "AZURE_TENANT_ID",
        "KEYVAULT_NAME",
        "KEYVAULT_SECRET_NAME",
        "GITHUB_TOKEN",
        "GITHUB_ENTERPRISE",
    ]

    missing: list[str] = [v for v in required_vars if not os.getenv(v)]
    if missing:
        raise EnvironmentError(f"Missing required environment variables: {missing}")

    return Config(
        azure_client_id=os.environ["AZURE_CLIENT_ID"],
        azure_client_secret=os.environ["AZURE_CLIENT_SECRET"],
        azure_tenant_id=os.environ["AZURE_TENANT_ID"],
        keyvault_name=os.environ["KEYVAULT_NAME"],
        keyvault_secret_name=os.environ["KEYVAULT_SECRET_NAME"],
        github_token=os.environ["GITHUB_TOKEN"],
        github_enterprise=os.environ["GITHUB_ENTERPRISE"],
        request_timeout=int(os.getenv("REQUEST_TIMEOUT", "10")),
        max_retries=int(os.getenv("MAX_RETRIES", "3")),
    )


# ----------------------------------------------------------------------
# Azure Key Vault
# ----------------------------------------------------------------------
def get_secret_from_keyvault(config: Config) -> str:
    credential = ClientSecretCredential(
        tenant_id=config.azure_tenant_id,
        client_id=config.azure_client_id,
        client_secret=config.azure_client_secret,
    )

    vault_url = f"https://{config.keyvault_name}.vault.azure.net"

    client = SecretClient(vault_url=vault_url, credential=credential)

    logging.info("Fetching secret from Key Vault")

    secret = client.get_secret(config.keyvault_secret_name)
    if not secret.value:
        raise ValueError("Secret retrieved but value is empty")

    return secret.value


# ----------------------------------------------------------------------
# GitHub API Client
# ----------------------------------------------------------------------
class GitHubClient:
    def __init__(self, config: Config) -> None:
        self.base_url = "https://api.github.com"
        self.enterprise = config.github_enterprise
        self.timeout = config.request_timeout
        self.max_retries = config.max_retries
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {config.github_token}",
                "Accept": "application/vnd.github+json",
            }
        )

    def _request(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> requests.Response:
        for attempt in range(self.max_retries):
            try:
                response = self.session.request(
                    method,
                    url,
                    timeout=self.timeout,
                    **kwargs,
                )
                if response.status_code >= 500:
                    raise requests.HTTPError(f"Server error {response.status_code}")
                return response
            except Exception as exc:
                logging.warning(f"Request failed (attempt {attempt + 1}): {exc}")
                time.sleep(2**attempt)

        raise RuntimeError(f"Request failed after {self.max_retries} retries")

    def list_orgs(self) -> list[str]:
        orgs: list[str] = []
        page = 1

        logging.info("Enumerating enterprise organizations")

        while True:
            url = (
                f"{self.base_url}/enterprises/"
                f"{self.enterprise}/organizations?page={page}&per_page=100"
            )
            response = self._request("GET", url)
            response.raise_for_status()

            data: list[dict[str, object]] = response.json()

            if not data:
                break

            for org in data:
                login = org.get("login")
                if isinstance(login, str):
                    orgs.append(login)

            page += 1

        logging.info(f"Discovered {len(orgs)} organizations")
        return orgs

    def update_org_secret(self, org: str, secret_name: str, secret_value: str) -> None:
        # Get public key
        key_url = f"{self.base_url}/orgs/{org}/actions/secrets/public-key"
        key_response = self._request("GET", key_url)
        key_response.raise_for_status()
        key_data: dict[str, str] = key_response.json()

        encrypted_value = self._encrypt_secret(key_data["key"], secret_value)

        put_url = f"{self.base_url}/orgs/{org}/actions/secrets/{secret_name}"
        payload = {
            "encrypted_value": encrypted_value,
            "key_id": key_data["key_id"],
            "visibility": "all",
        }

        response = self._request("PUT", put_url, json=payload)
        response.raise_for_status()

    @staticmethod
    def _encrypt_secret(public_key_str: str, secret_value: str) -> str:
        public_key_obj = public.PublicKey(
            public_key_str.encode("utf-8"),
            encoding.Base64Encoder,
        )
        sealed_box = public.SealedBox(public_key_obj)
        encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
        return base64.b64encode(encrypted).decode("utf-8")


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------
def main() -> None:
    log_level = os.getenv("LOG_LEVEL", "INFO")
    configure_logging(log_level)

    try:
        config = load_config()
        secret_value = get_secret_from_keyvault(config)

        github = GitHubClient(config)
        orgs = github.list_orgs()

        for org in orgs:
            logging.info(f"Updating {config.keyvault_secret_name} for org={org}")
            github.update_org_secret(org, config.keyvault_secret_name, secret_value)

        logging.info("All organizations updated successfully")

    except Exception as exc:
        logging.exception(f"Fatal error: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
