# Setup and operations

## Configuration lives in three places

| Location | Purpose |
| --- | --- |
| `.env` and Compose | Bind address/access token, host mounts, optional first-start manager credentials, resources. |
| Settings in the app | Connections, path mappings, monitored-folder rules, word list, strategies, output policy, review thresholds, retention, optional Plex/email. |
| Persistent mounts | SQLite/jobs under `/data`, local models under `/models`, media under `/media`, separate output under `/output`, originals under `/originals`. |

The repository ships no active connections, keys, libraries, email accounts, or personal media paths. Bootstrap environment values do not override previously saved database settings. Blank secret inputs preserve saved values; clearing a manager URL disconnects it.

## Mounts and path mapping

A mount makes a host directory visible in the container. A path mapping translates what Sonarr/Radarr reports into that container path. They solve different problems.

Example: host media `/srv/library` is mounted at `/media`; Sonarr reports `/srv/library/TV/Example/episode.mkv`. Set Sonarr mapping from `/srv/library` to `/media`. If Radarr uses a different prefix, configure its mapping separately. Allowed destinations must remain under `MEDIA_ROOTS` (default `/media`).

Compose mounts media read-only. To enable same-folder output:

1. Stop automatic queuing and wait for the current job to finish.
2. Change the media mount from `:/media:ro` to `:/media:rw`.
3. Recreate the container with `docker compose up -d`.
4. Select the policy in Settings and process one file first.

The archive must not be a child of a scanned Plex or manager library. For example, `/srv/bleeparr-originals` can be separate from `/srv/library`. In replacement mode, verified copies go there before source deletion. Keep archive and output mounts persistent across container recreation.

## Models and resources

Download the configured models once using the README setup command. Models persist in `./models`, mounted at `/models`. Recognition sets offline mode and never downloads missing weights implicitly. A provider search for subtitles or a manager API call is a separate network operation.

Defaults are CPU/INT8/two threads, with small then medium. Intel integrated graphics is not CUDA. The supplied image does not configure NVIDIA support. Changing device/compute options requires a compatible runtime and an actual idle readiness check. Four gigabytes is the default container limit, not a promise every model/device combination will fit. Avoid concurrent inference processes on small hosts.

FSM avoids word-refinement inference but still performs sampled speech timing while that guard is enabled. Turning off a safeguard is a deliberate reduction in evidence, not a fix for a broken model runtime.

## Everyday use

- Preview folder rules with automatic queuing paused. Enabling automatic queuing includes existing media.
- Check the first cleaned file with a media player before adopting replacement mode broadly.
- Review the Activity result and suggested steps. Use the bounded technical log when needed.
- Correct title/timing/subtitle problems before Retry. Broad-muting approval applies only to the displayed unchanged plan.
- Use Reprocess on a completed item to preview one current source. Retained originals are available only through explicit reprocessing; automatic scans do not repeatedly process them.
- Temporary retention defaults off; when enabled, adjust days/capacity to your needs. A full archive blocks replacement. Increase capacity, wait for expiry, or explicitly disable retention; unchanged originals are not evicted early.
- Renamed replacement outputs request a manager refresh. Plex must index the new path separately before notes can be applied.

## Back up and upgrade

Back up `.env`, Compose customizations, the entire data directory, and model cache as needed. Data contains plaintext local credentials and personal paths; keep backups private. Original retention is not a permanent backup.

For a simple consistent upgrade:

1. Disable automatic queuing and wait until no job is running.
2. Record the current source version/image and resource/mount configuration.
3. Stop the container, then copy the entire data directory, including any SQLite WAL/SHM files.
4. Pull the desired release, inspect its migration notes, and rebuild with `docker compose up -d --build`.
5. Confirm `/api/health`, connection checks, archive mounts, and offline model readiness before resuming work.

Do not run two versions against the same data directory. Do not delete hidden `.bleeparr-job-*` stages or delivery receipts until their publication state has been reviewed. A restore after new files have been published can discard deduplication/publication evidence; reconcile the current files before restoring an older database. Database/schema/settings changes can make an older image incompatible even when the source code is available.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Manager cannot be reached | URL reachable from the container, API key, network/firewall, and optional manager URL base. Redirects are rejected. |
| File not visible | Host mount plus manager-to-container prefix mapping; allowed media roots and permissions. |
| Missing subtitles | English text track/sidecar availability; image subtitles need external OCR; provider availability is not guaranteed. |
| Language/coverage hold | Actual subtitle text and completeness; metadata tags alone cannot resolve it. |
| Timing hold | Subtitle release/cut matches audio; inspect sample results. No automatic offset correction is provided. |
| Speech-model error | Cached files, pinned decoder versions, available RAM, compute/device configuration; run readiness while idle. |
| Broad-muting review | Planned durations/locations, accurate subtitle text, speech evidence; do not approve solely to clear the queue. |
| Output unwritable | Read-only media mount or filesystem permissions; saving Settings cannot change either. |
| Original archive full | Actual archive contents, including partial/unregistered files, configured cap, free space, expiry. |
| Existing destination/stage | Review its signature/receipt before removing anything; unrelated files are not overwritten. |
| Plex note pending | Indexed exact output paths, library IDs, path mapping, mixed versions, token access. |
| Notification unknown | SMTP may already have accepted the message before interruption; review before retrying. |

Job logs and artifacts persist; original expiry cleanup does not prune general job history. API history is limited to 300 recent jobs and 20 events. Maintain storage with the app idle and retain publication/audit evidence required to explain current files.

## Auditing older completions

The scripts under `scripts/` support read-only history, subtitle-language, and speech-fallback audits, followed by an explicit reviewed import. Use each script's `--help` for its input/output contracts. Audit files contain private paths/logs and belong outside Git. Filename markers and old “no bad words” success logs are not reliable evidence of a cleaned file. Imports do not repair media or authorize automatic acceptance of questionable successes.
