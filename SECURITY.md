# Security and privacy

Bleeparr is an administrator tool with media write access when replacement is enabled. Use a trusted network, a strong `BLEEPARR_TOKEN` for LAN access, and an authenticated HTTPS reverse proxy for remote access. It has a shared access token rather than individual user accounts. The default Compose bind is localhost and media is read-only.

## Local sensitive data

Settings credentials are stored in the local SQLite database, not encrypted at rest. API responses omit manager keys, Plex tokens, and SMTP passwords. Empty secret fields preserve saved values. The process environment, `.env`, database/backups, logs, audit reports, job word lists, library paths, and email history can contain private data. Restrict filesystem access and scrub these before sharing.

Recognition runs offline against cached models. Initial setup downloads model weights. Manager APIs, optional subtitle providers, optional Plex, and optional SMTP communicate over their configured networks. “Local processing” does not mean every integration is network-free.

## Reporting

Do not post keys, raw database files, private URLs, or full personal logs in a public issue. Use GitHub's private vulnerability reporting option if enabled, or contact the repository owner through a private channel available on their profile. Provide a minimal synthetic reproduction and redact hostnames, paths, tokens, and account details.

## Historical credentials

Earlier source versions contained deployment values. The 3.0 source and archived snapshots are scrubbed. Removing values from Git does not revoke them or remove third-party clones/caches. Rotate any key previously published, and use GitHub support procedures if cached sensitive content needs removal. Never reintroduce the old unsanitized history into a clean public branch.
