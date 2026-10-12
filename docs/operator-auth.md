# Local operator authentication

Every workflow route requires a bearer credential. `GET /health` remains public;
it reveals only process liveness. `GET /auth/me` returns the authenticated actor's
name, human/service classification, and roles, never a token or its digest.

## Provision an operator

Run locally from the repository root:

```powershell
.\.venv\Scripts\python.exe scripts/create_operator.py --operator alice
$env:REKIT_AUTH_CONFIG_PATH = '.\.secrets\operators.json'
```

The command generates a random 32-byte token, stores its SHA-256 digest and actor
configuration, and prints the secret token once. Keep that output private. It
refuses to overwrite an existing config. The default grants all six roles to the
named human; use `--roles viewer intake` for a narrower credential. The `.secrets/`
directory is ignored by Git. Restrict its filesystem permissions to the backend
owner; this helper does not administer Windows ACLs.

Set the catalog, policy, and database paths described in [API setup](api-workflow.md)
and start the configured app factory. Auth configuration is validated before
database initialization. There is no default password, public registration,
permissive development mode, or fallback when credentials are missing.

Requests use `Authorization: Bearer <token>`. Enter the token in the local operator
interface when that interface is running. Do not put it in a URL, frontend build
variable, browser storage, Git, or server logs. No cookie or external identity
provider is used. Restart the backend after editing or revoking credentials.

## Server-owned roles

| Role | Permission |
| --- | --- |
| `viewer` | Read workflow records. |
| `intake` | Register batches, returns and components; record unverified evidence. |
| `reviewer` | Human identity verification and corrections. |
| `planner` | Request recovery proposals from server inventory and policy. |
| `approver` | Human approval/reservation and cancellation. |
| `executor` | Human completion confirmation. |

Every authenticated actor can read `/auth/me`, including actors without `viewer`.
Roles are explicit; one role does not imply another. Sensitive routes require
both a human principal and the relevant role. Service principals cannot be
configured with reviewer, approver, or executor roles, and cannot assert an
operator-sourced observation. Models and integrations must receive only service
credentials, never a human operator's token.

Public verification and execution requests no longer accept `operator_id`.
The API constructs domain commands with the authenticated actor before checking
versions and idempotency. An exact retry by the same authorized actor remains
idempotent; another actor cannot reuse that request's operation ID. Credentials
and roles are checked before replaying a past successful operation.

Human observation/uncertainty source references are bound to the authenticated
actor. Planner audit records identify the requester. Existing capture/verification
timestamps remain reported metadata; server-recorded event timestamps establish
when an assertion entered the database. Authentication does not validate its truth.

## Threat model and limits

This design protects a local API from unauthenticated callers and prevents service
credentials or arbitrary body fields from granting human authority. Tokens use
Python's [cryptographic secrets generator](https://docs.python.org/3.12/library/secrets.html)
and constant-time digest comparison. Hashing is suitable here for high-entropy
random tokens; this is not a password-storage design or an OAuth authorization server.

Possession of a bearer token grants its authority. A stolen or shared human token
can impersonate its owner; the human classification does not prove someone is
physically present. Protect tokens in storage and transit, as described by
[RFC 6750](https://www.rfc-editor.org/rfc/rfc6750). Bind both development servers to
loopback. Public/network deployment requires TLS and additional operational controls.

The trusted boundary includes the local backend process, its configuration, and
database/filesystem owner. Local administrators or malware can alter these or
inspect process/browser memory. There is no MFA, automatic expiry, account recovery,
multi-tenant isolation, or password/account-management platform. Revocation takes
effect after configuration reload by restarting the process. Authentication failures
must not write evidence, reservations, completions, or audits.
