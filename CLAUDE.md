# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt       # runtime deps
pip install -r requirements.dev.txt   # dev deps (ruff, mypy, types-requests)
```

Copy `.env.example` to `.env` and fill in all required values before running.

## Commands

```bash
# Lint and type-check
source .venv/bin/activate && make lint    # ruff format + ruff check --fix + mypy --strict

# Run
source .venv/bin/activate && make run
```

## Architecture

Single-file script (`main.py`) with three logical layers:

1. **Config** — `load_config()` reads all required env vars into a frozen `Config` dataclass. Fails fast if any are missing.

2. **Azure Key Vault** — `get_secret_from_keyvault()` uses a service principal (`ClientSecretCredential`) to retrieve the secret from Azure Key Vault.

3. **GitHub API** — `GitHubClient` wraps `requests.Session` with retry/backoff logic. It:
   - Paginates `GET /enterprises/{enterprise}/organizations` to discover all orgs
   - For each org, fetches the Actions public key, encrypts the secret with NaCl `SealedBox`, and `PUT`s it to `orgs/{org}/actions/secrets/{KEYVAULT_SECRET_NAME}` with `visibility: all`

All output is structured JSON logs via a custom `JsonFormatter`.

## Environment Variables

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `AZURE_CLIENT_ID` | yes | — | Service principal client ID |
| `AZURE_CLIENT_SECRET` | yes | — | Service principal secret |
| `AZURE_TENANT_ID` | yes | — | Azure AD tenant |
| `KEYVAULT_NAME` | yes | — | Key Vault name (not full URL) |
| `KEYVAULT_SECRET_NAME` | yes | — | Name of the secret to fetch |
| `GITHUB_TOKEN` | yes | — | PAT with enterprise + org secrets write scope |
| `GITHUB_ENTERPRISE` | yes | — | GitHub Enterprise slug |
| `LOG_LEVEL` | no | `INFO` | Logging verbosity |
| `REQUEST_TIMEOUT` | no | `10` | HTTP timeout in seconds |
| `MAX_RETRIES` | no | `3` | Retry attempts with exponential backoff |
