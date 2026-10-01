# Changelog

## Unreleased

- Recover automatically from rejected subtitle language, coverage and timing by trying other sidecars, embedded tracks, and up to five ranked Subliminal results. Use canonical manager identity and release details; require downloaded candidates to match sampled speech before processing.
- Add an online subtitle search setting and show candidate decisions in Activity. Preserve selected extracted/downloaded subtitles for original retention.

## 3.0.0 — 2026-09-30

Complete rewrite of the web application formerly called Bleeparr 2.0.

- FastAPI/React interface with a durable SQLite queue, restart recovery, monitoring, library filters, and readable Activity results.
- Local speech refinement with a pinned compatible decoder/runtime; dependency failures cannot silently become subtitle fallback.
- English audio selection, actual subtitle language/coverage checks, sampled timing checks, and internal title/cut verification.
- Distinct no-match and skipped outcomes; scoped review before unusually broad muting.
- Full decode validation, guarded replacement, durable publication receipts, and explicit targeted reprocessing.
- Optional bounded original retention outside libraries, with verified copies and expiry-aware reprocessing.
- Offline model readiness checks; optional Plex notes, SMTP outbox, and verified damaged-release recovery.
- Generic setup defaults, complete operator/maintainer documentation, synthetic screenshots, MIT license, and app icon.

The bundled processing CLI is carried forward unchanged by this web-release preparation. No changes are made to the separate CLI project. There is no automatic migration from legacy databases or old success labels.

## Earlier versions

The legacy web application was named 2.0, with repository tags in the `v0.2.0*` family. Scrubbed source snapshots are retained for reference; they are unsupported.
