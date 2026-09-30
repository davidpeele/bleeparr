# Version 3.0 migration

Version 3.0 denotes a replacement of the 2.0 web architecture rather than a small compatibility update. It introduces a single durable queue, explicit processing outcomes, guarded publication, and local evidence checks. The previous repository tags used `v0.2.0*` even though the application was called Bleeparr 2.0.

## New installation recommended

Keep old data privately. Install 3.0 into a fresh directory, stop legacy monitor scripts, provision local models, reconnect your managers, map paths, and reselect titles. There is no automatic conversion of old databases, settings, or success labels. Start with read-only media and separate output, then deliberately enable replacement after checking a result.

The bundled `cli/` is required by the web app and is carried forward unchanged in this release. The separate CLI version/project is outside this web-release scope. Do not run its older monitor against the same workflow at the same time.

## Legacy archive

The release preparation preserves the earlier main/development source and tagged versions as scrubbed source snapshots. Personal endpoints and embedded credentials are removed. Archive snapshots are for historical reference, not supported deployments.

Publishing scrubbed snapshots does not revoke any previously exposed secret or erase copies held elsewhere. Rotate credentials that appeared in earlier public source. If Git history is replaced to remove sensitive ancestry, existing clones must be recloned or deliberately reconciled; do not merge old history back into the public release.

## Maintainer compatibility notes

- Persistent web data is `bleeparr-v3.sqlite3`; do not infer compatibility from an older DB filename.
- New default settings insert only missing keys. Existing users retain their own configured values.
- Defaults leave queuing, destructive recovery, Plex/email, and temporary retention off; media is read-only and separate output is selected.
- No default manager URLs, keys, folder-selection roots, or Plex account values are supplied.
- Speech dependencies remain pinned to the validated group. Model downloads happen separately at setup.
- See the technical reference before modifying job states, receipts, archive expiry, or reprocessing.
