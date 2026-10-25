# Troubleshooting

## Azure Authentication

### `DefaultAzureCredential` fails on first run (IMDS timeout)

**Symptom:** The first pipeline run fails with a long error listing all attempted credentials:
```
DefaultAzureCredential failed to retrieve a token from the included credentials.
Attempted credentials:
  ManagedIdentityCredential: ManagedIdentityCredential authentication unavailable, no response from the IMDS endpoint.
  AzureCliCredential: Failed to invoke the Azure CLI
  ...
```

**Cause:** `DefaultAzureCredential` tries `ManagedIdentityCredential` early in its chain. On a local dev machine, this attempts to contact the IMDS endpoint which doesn't exist locally, so it blocks until the network timeout (~5-10s). This can exhaust the overall credential chain timeout or cause cascading failures before `AzureCliCredential` gets a chance to run.

This is expected behavior — `DefaultAzureCredential` probes the IMDS endpoint to detect the hosting environment, and the timeout is unavoidable on local machines unless the credential chain is configured to skip it.

**Fix:** Set the `AZURE_TOKEN_CREDENTIALS` environment variable to `dev` to exclude deployed-service credentials (e.g. `ManagedIdentityCredential`, `WorkloadIdentityCredential`) from the chain, so `DefaultAzureCredential` skips straight to developer-tool credentials like `AzureCliCredential`:

```bash
# PowerShell
$env:AZURE_TOKEN_CREDENTIALS = "dev"

# Bash / Linux / macOS
export AZURE_TOKEN_CREDENTIALS=dev
```

Or add `AZURE_TOKEN_CREDENTIALS=dev` to your `.env` file.

> Requires `azure-identity >= 1.23.0`. See [Exclude a credential type category](https://learn.microsoft.com/azure/developer/python/sdk/authentication/credential-chains?tabs=dac#exclude-a-credential-type-category) for details.

### Prerequisite: `az login`

The pipeline uses Azure AD token-based auth. You must be logged in:
```bash
az login
az account show  # verify
```
