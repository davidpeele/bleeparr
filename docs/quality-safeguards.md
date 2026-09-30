# Quality safeguards

New app installations and existing installations enable title verification, sampled subtitle timing, and broad-muting review. Temporary original retention is **off by default**. Settings apply when a job starts; completed files are not automatically reprocessed.

## Title and cut verification

Bleeparr compares usable internal media titles, years, episode numbers, and runtime against Sonarr/Radarr metadata. Conflicts require review before rendering. Missing titles and generic encoder labels are reported as unavailable; filenames alone cannot establish identity. Runtime differences exceeding the larger of five minutes and 15% require review and can represent a different cut.

## Subtitle timing

Up to six dialogue cues distributed across the program are checked against local speech recognition. The small model runs first; the fallback model checks unconfirmed samples. At least two thirds of samples must match. Insufficient dialogue or mismatched timestamps requires review. Runtime dependency errors stop processing. Passing verifies sampled dialogue only, and does not prove complete coverage or automatically adjust timestamps.

## Broad muting

Defaults require review when subtitle fallback covers more than 25% of matched sections (with at least three fallback sections), total muting exceeds 3% of program duration, or any fallback mute exceeds 10 seconds. The Activity review shows mute counts, durations, and locations before publication.

An explicit approval applies only to the same source, subtitle, word list, speech models, buffers, limits, and exact mute ranges. Reprocessing checks them again. Title and timing holds cannot be overridden through the broad-muting approval.

## Temporary originals

Enable retention in Settings only when desired. Optional defaults are seven days and 100 GB. Compose mounts `ORIGINALS_PATH` at `/originals`; keep this archive outside manager movie and episode folders. Before replacement, Bleeparr verifies a copy of the original and selected subtitle. Reprocess can use that copy while its signatures remain unchanged.

The capacity includes partial and unregistered archive files. If full, replacements wait; unexpired originals are never discarded to make room. Cleanup removes only expired registered copies whose signatures are unchanged. An active reprocessing job pins its original until it finishes. Modified copies are preserved for review. Original retention is temporary recovery storage, not a permanent backup.

## Speech-model readiness

Settings shows cached models and installed dependencies. Save & check models runs both configured models offline against a short local audio sample, including lazy audio decoding. Checks run only when processing is idle and block competing worker claims. Reports become outdated when model files, dependencies, or relevant settings change. This checks runtime compatibility; it does not measure recognition accuracy.

## CLI

Standalone CLI checks are explicitly enabled with `--expected-identity` (manager metadata JSON), `--check-subtitle-timing`, and `--review-broad-muting`. Thresholds use `--max-fallback-percent`, `--max-muted-percent`, and `--max-fallback-seconds`. The app supplies these flags from Settings. Retention is managed by the app publication layer.

## Coverage review thresholds

For programs at least ten minutes long, review flags fewer than 0.5 dialogue cues per minute, fewer than eight words per minute, or dialogue intervals covering less than 5% of duration. It also flags an opening gap exceeding both three minutes and 10% of duration, or an ending/internal gap exceeding both five minutes and 15%. Overlapping cues count once. Quiet scenes and credits can cause false positives; passing does not prove completeness.

## Verification

The 3.0 processing baseline passed 206 Linux Python regression tests and 13 frontend tests, plus frontend lint/build and desktop/mobile review checks. Live offline model checks verified both configured models; a read-only reference sample confirmed all six distributed dialogue cues. Personal deployment reports and media details are not included in the release.
