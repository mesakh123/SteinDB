# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability, please report it responsibly:

- **Email**: cmesakh@ymail.com
- **Response time**: 72-hour acknowledgment
- **Do NOT** open a public GitHub issue for security vulnerabilities

## Security Design

- **Offline-first**: The CLI runs entirely locally. No customer code is transmitted unless you explicitly use the cloud API.
- **BYOK**: When using AI-assisted conversion, you provide your own API key. SteinDB never stores or proxies your credentials.
- **No telemetry by default**: Anonymous usage telemetry is opt-in only.

## Scope

We consider the following as security issues:
- Customer Oracle/PostgreSQL code exposure
- API key leakage
- Prompt injection that causes incorrect SQL generation
- Authentication/authorization bypasses in the cloud API
