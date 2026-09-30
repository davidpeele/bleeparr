# Contributing

Read [the technical reference](docs/technical-reference.md) before changing processing or publication. Keep examples, test fixtures, logs, screenshots, and issue attachments free of real keys, addresses, media-library paths, and account details.

## Local development

Use Python 3.12, Node.js 22, and installed FFmpeg/FFprobe:

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install -r requirements-dev.txt
cd frontend
npm ci
npm run build
cd ..
DATA_DIR=./data MEDIA_ROOTS="$PWD/media" OUTPUT_DIR="$PWD/cleaned" \
BLEEPARR_CLI="$PWD/cli/bleeparr.py" DISABLE_WORKER=1 \
.venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port 5050
```

`DISABLE_WORKER=1` disables media/mail workers for safe UI work. Use isolated synthetic data; do not point development at a production data directory. For hot reload, run `npm run dev` in `frontend`; Vite proxies `/api` to port 5050.

## Checks

```sh
.venv/bin/python -m pytest tests -q
node --test frontend/tests/*.mjs
npm --prefix frontend run lint
npm --prefix frontend run build
```

Full media tests require FFmpeg and the installed speech dependencies. A skipped decoder test does not establish compatibility. Tests mock managers, Plex, and SMTP; they do not require real secrets or model downloads. Actual cached-model inference is a separate offline smoke check when changing speech dependencies.

## Changes that need particular care

- Preserve transactional claims, restart recovery, receipts, signatures, and no-clobber publication.
- Exercise changed-source, interrupted-publication, full-archive, expired-original, and duplicate-action cases.
- Keep no-match/foreign/review outcomes separate from a cleaned success.
- Do not use subtitle fallback to hide dependency failures.
- Keep manager recovery limited to verified invalid-media failures.
- Keep API secrets redacted and blank-secret preservation deliberate.
- Keep mobile controls accessible and status text understandable without color alone.
- Add safe migrations rather than resetting existing settings.
- Update the relevant documentation/changelog alongside behavioral changes.

## Screenshots and branding

`scripts/capture_screenshots.mjs` captures the built app using synthetic API responses and blocks non-local network requests. Start a local static server for `frontend/dist`, then run the script with `BLEEPARR_SCREENSHOT_URL` and, if needed, `BLEEPARR_BROWSER` set. Install Playwright locally for this task. No production backend is needed.

The icon prompt and generation provenance are in [asset notes](docs/assets/README.md). Assets are local; screenshots contain fictional titles. Do not substitute a production Settings screenshot.

## Release

Follow [operations](docs/operations.md) and [security](SECURITY.md). Review the exact tracked/exported files, not just ignore patterns. Exclude `.env`, database files, models, media, logs, job artifacts, personal deployment notes, and private history bundles. Verify the source archive contains no private history. Tag the documented version only after the clean publication plan is approved.
