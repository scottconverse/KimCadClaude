# Security Policy

KimCad is a beta-stage, local-first tool. Please report security issues **privately** —
use GitHub's [private vulnerability reporting](../../security/advisories/new) (Security →
Report a vulnerability) rather than opening a public issue.

## What To Include

- The affected command, route, or workflow.
- Exact reproduction steps.
- Any generated files needed to reproduce the issue.
- Whether the issue involves generated code, printer credentials, local files,
  cloud API keys, or network exposure.

## Current Trust Boundary

KimCad is designed to run on a trusted user's own Windows machine. The web server
binds to loopback by default, generated CAD code is sandboxed and validated
before slicing, and printer sends require explicit confirmation.

**Session token (KC-26).** State-changing requests carry a per-boot random token (issued by the
server, injected into the page shell, returned as the `X-KimCad-Session` header; constant-time
compared, `403` on mismatch). This is **defense-in-depth against a drive-by cross-origin POST**
from a malicious web page — which can reach loopback but cannot read the same-origin token — and
is deliberately **not** full CSRF protection (a single-user loopback app has no cookie session to
forge) and **not authentication**. In particular it does **not** secure `--allow-remote`: any
client that can load the page over HTTP reads the token, so a remotely-exposed instance is still
unauthenticated and needs a separate auth layer (see below). Side-effecting GETs that can't carry
the token (the lazy STEP build, the health re-probe) refuse a cross-origin request via
`Sec-Fetch-Site`. Full detail: [`docs/api.md`](docs/api.md) (Security model).

Do not expose `kimcad web` on an untrusted network without a separate
authentication layer. Real printer validation is intentionally deferred until
the post-Stage-11 hardware phase.
