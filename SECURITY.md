# Security Policy

## Reporting a Vulnerability

If you find a security vulnerability in **hermes-brain**, please use [GitHub's Private Vulner Reporting](https://github.com/MNDL-27/hermes-brain/security/advisories/new) to report it.

This creates an encrypted, private report visible only to the maintainer. Do **not** open a public issue — that exposes the vulnerability to everyone before a fix is available.

### What to include in your report

- Description of the vulnerability
- Steps to reproduce (reproducible PoC is best)
- Potential impact (data leak, token exposure, etc.)
- Your contact info (optional but helpful for coordination)

### What to expect

- Acknowledgment within **48 hours**
- Fix timeline: within **7 days** for confirmed issues
- A private advisory on the repo once the fix is ready

## What this covers

Secrets leaked into stored memory (Notion), tool call injection, provider credentials, cache files (`notion_brain.json`), and the bootstrap process. If your report concerns any of these, prioritize it.

## What does not apply

Misconfigured integrations, revoked tokens, or account-level access issues on Notion/Stripe/etc. — these are configuration problems, not vulnerabilities in the code.
