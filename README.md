# github-token-orgs-deployer

Deploys a secret from Azure Key Vault to all GitHub organizations in a GitHub Enterprise as an Actions org-level secret.

## What it does

1. Authenticates to Azure Key Vault using a service principal
2. Retrieves the target secret from Key Vault
3. Enumerates all organizations in the GitHub Enterprise via pagination
4. Encrypts the secret with each org's NaCl public key
5. Upserts the secret (named by `KEYVAULT_SECRET_NAME`) with `visibility: all` on every org

All output is structured JSON logs.

## Requirements

- Python 3.10+
- An Azure service principal with `Get` access to the target Key Vault secret
- A GitHub PAT with `admin:enterprise` and `admin:org` scopes (secrets write)

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Copy the example env file and fill in all values:

```bash
cp .env.example .env
```

## Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `AZURE_CLIENT_ID` | yes | — | Service principal client ID |
| `AZURE_CLIENT_SECRET` | yes | — | Service principal secret |
| `AZURE_TENANT_ID` | yes | — | Azure AD tenant ID |
| `KEYVAULT_NAME` | yes | — | Key Vault name (not the full URL) |
| `KEYVAULT_SECRET_NAME` | yes | — | Name of the secret to fetch |
| `GITHUB_TOKEN` | yes | — | PAT with enterprise + org secrets write scope |
| `GITHUB_ENTERPRISE` | yes | — | GitHub Enterprise slug |
| `LOG_LEVEL` | no | `INFO` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `REQUEST_TIMEOUT` | no | `10` | HTTP timeout in seconds |
| `MAX_RETRIES` | no | `3` | Retry attempts with exponential backoff |

## Usage

```bash
source .venv/bin/activate && make run
```

Or directly:

```bash
source .venv/bin/activate && python main.py
```

## Development

Install dev dependencies (ruff, mypy):

```bash
source .venv/bin/activate
pip install -r requirements.dev.txt
```

Lint and type-check:

```bash
source .venv/bin/activate && make lint
```

## Dependencies

| Package | Purpose |
|---|---|
| `azure-identity` | Service principal authentication |
| `azure-keyvault-secrets` | Key Vault secret retrieval |
| `requests` | GitHub API HTTP client |
| `pynacl` | NaCl sealed-box encryption for GitHub secrets |
| `python-dotenv` | `.env` file loading |
