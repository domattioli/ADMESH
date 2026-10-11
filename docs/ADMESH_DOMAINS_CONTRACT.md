# Registry API contract

This document records what ADMESH relies on from the Valence mesh API. The
source of truth is the Valence repository, spec `001-token-gated-mesh-api`.
ADMESH 1.0.5 and later do not install or import any Valence package. The
client is `admesh/_registry_client.py` and uses only the standard library.

## Configuration

| Variable | Use |
|---|---|
| `VALENCE_TOKEN` | Required. Sent as a bearer token. Never logged or echoed. Tokens expire after one year. |
| `VALENCE_API_URL` | Base URL. Required while no default URL is built in. |

## Requests

| Request | Success | Errors handled |
|---|---|---|
| `GET /meshes` | JSON list of names | 401, 429, 5xx |
| `GET /meshes/{name}` | fort.14 bytes | 401, 404, 429, 5xx |
| `GET /meshes/{name}/hash` | JSON `{sha256}` | 401, 404, 429, 5xx |

Each request has a 10 s timeout. The API allows 120 requests per minute.
The payload must match `sha256`, or the mesh is rejected.

## Errors

| Condition | Exception |
|---|---|
| No token | `RegistryAuthError` ("Valence registry needs a token"), raised before any network call |
| 401 | `RegistryAuthError` (token invalid or expired) |
| 404 | `RegistryNotFoundError` (also a `ValueError`) |
| 429, 5xx, no URL, connection failure, timeout | `RegistryUnavailableError` ("Valence registry API unavailable") |
| Hash mismatch | `RegistryIntegrityError` |

All inherit from `RegistryError`.
