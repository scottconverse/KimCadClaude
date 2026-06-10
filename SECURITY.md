# Security Policy

KimCad is an early-development, local-first tool. Please report security issues
privately to the repository owner instead of opening a public issue.

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

Do not expose `kimcad web` on an untrusted network without a separate
authentication layer. Real printer validation is intentionally deferred until
the post-Stage-11 hardware phase.
