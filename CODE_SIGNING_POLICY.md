# Code Signing Policy

This project signs and distributes release artifacts.

## Windows — SignPath Foundation
Free code signing provided by SignPath.io, certificate by SignPath Foundation.

### What is signed
- Windows installer/executable artifacts published on GitHub Releases

### Build and signing process
- Artifacts are built from this repository using GitHub Actions (GitHub-hosted runners only)
- Only CI-built artifacts are submitted to SignPath for signing
- The private key is held by SignPath (HSM-backed); this project does not store the private key

### Team roles
- Author (commit access): https://github.com/scottconverse
- Approver (approves each signing request): https://github.com/scottconverse
- Policy: Each signing request requires explicit approval by the maintainer

## Distribution
Signed releases are published at: https://github.com/scottconverse/KimCadClaude/releases

## Privacy
This software will not transfer any information to other networked systems unless specifically requested by the user.
