---
type: Learning Note
title: Secure coding
description: Awareness of common vulnerabilities and safe patterns.
tags: [security, owasp, secure-coding, learning]
timestamp: 2026-06-18T09:00:00Z
---

# Why

At a bank, security is not optional. Secure coding prevents vulnerabilities and protects data.

# OWASP Top 10 awareness

- Injection (SQL, command).
- Broken access control.
- Insecure configuration.
- Vulnerable and outdated dependencies.
- Insufficient logging and monitoring.

# Safe habits

- Validate and sanitize input at system boundaries.
- Use parameterized queries.
- Don't store secrets in code; use a secrets store.
- Apply least privilege.
- Keep dependencies up to date.

# Notes

- 

# Related

- [Backend development](backend-development.md)
- [Technical decisions](../decisions/technical-decisions.md)
