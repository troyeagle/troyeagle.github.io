# Static application synchronization

The first application is `troyeagle/larp-clues-presentation` → `/clue/`.
Jekyll, Hux templates, article files and all other application directories keep
their existing layout. Source code continues to live in its own repository.

## Workflow

1. The source workflow tests and builds the application on `main`.
2. It uploads `site-clue`, including `_site-sync.json` with the source SHA,
   workflow run identity and SHA-256 hashes for every file.
3. A separate notification job dispatches `sync-apps.yml` on this repository's
   `master`. Without the notification credential, manual and scheduled collection
   remain available.
4. The collector accepts only the configured workflow, branch and completed
   successful build job. It checks source ancestry, the artifact digest, manifest
   identity, file hashes, paths and HTML asset references.
5. A separate publishing job revalidates the staged files against the latest
   policy and state, replaces only the configured app directories and commits
   their changes together with `.github/apps-state.json`.

All notifications use the same synchronization workflow. Each run checks every
configured application; coalescing pending runs therefore does not drop one
application's update. A schedule at minutes 17 and 47 repairs missed notifications;
GitHub schedules are best-effort and may run late.

## Credentials

Preferred: create a GitHub App owned by `troyeagle`, installed only on
`larp-clues-presentation` and `troyeagle.github.io`. Give the installation
`Contents: read/write` and `Actions: read`. Store:

| Blog setting | Value |
| --- | --- |
| Repository variable `SITE_SYNC_APP_ID` | App ID |
| Repository secret `SITE_SYNC_APP_PRIVATE_KEY` | App private key |

The collector requests an installation token scoped to the source repository
with **Contents read, Actions read**. The publisher requests a different token
scoped to **the blog only, Contents write**. The private key is stored only in
the blog repository, and source build jobs never receive it.

An alternative for the pilot is two fine-grained personal access tokens stored
only in the blog:

| Blog secret | Repository scope | Permissions |
| --- | --- | --- |
| `SOURCE_ARTIFACTS_TOKEN` | `larp-clues-presentation` | Contents read, Actions read |
| `BLOG_PUBLISH_TOKEN` | `troyeagle.github.io` | Contents write |

For immediate notifications, create a separate fine-grained token scoped only
to **troyeagle.github.io, Actions write**, and store it as `BLOG_DISPATCH_TOKEN`
in **larp-clues-presentation**. This token cannot write blog contents. The
notification job is separate from the job executing application code.

Use Actions secrets; do not place keys or tokens in files or chat messages.
Fine-grained PATs expire and require renewal. GitHub App installation tokens
are generated per job and automatically revoked by the official action.

## Enable the pilot

1. Land the receiver on blog `master`; land the source workflow on source `main`.
2. Configure the credentials above. Keep automatic collection disabled while
   the workflows and credentials are being installed.
3. Set the blog repository variable `SITE_SYNC_ENABLED` to `true`. Keep
   `SITE_SYNC_PUBLISH_ENABLED` unset or `false`. Collection and validation can
   run, but every publishing job is skipped until the second flag is enabled.
4. Run **Build static application** in the source repo if no artifact is ready.
5. Run **Sync static applications** in the blog with `dry_run: true` (the default).
   Inspect its summary and the `prepared-static-updates` artifact. No write
   credential is generated and no commit is made during this run.
6. After reviewing the preview, set `SITE_SYNC_PUBLISH_ENABLED` to `true`, then
   run it again with `dry_run: false` to publish. Verify the resulting commit
   touches only `clue/` and `.github/apps-state.json`, then check the normal
   GitHub Pages deployment and `/clue/`.
7. Configure `BLOG_DISPATCH_TOKEN` when the first publish is verified, so future
   source updates immediately request synchronization.

Once both flags are enabled, scheduled runs can publish automatically. Collection
can remain enabled indefinitely with publishing disabled. Do not configure
notification credentials until the first publish is verified.

Branch-based GitHub Pages does not build on pushes made with `GITHUB_TOKEN`.
The publishing job therefore uses the installation token or `BLOG_PUBLISH_TOKEN`,
not the workflow's default token. Existing Pages settings remain branch-based.

## Scope and recovery

- `.github/apps.json` is the trusted allowlist. An event cannot supply a source
  repository, target path, shell command or download URL.
- Only `clue` is configured for the pilot. Other directories are untouched.
- Failed builds are skipped. Invalid downloaded artifacts fail validation
  before any published directory is replaced.
- Every file must be listed in the manifest. Symlinks, special files, hidden
  paths, source directories and traversal paths are rejected. Output size and
  entry count are bounded. HTML assets must resolve inside the app directory.
- Source maps are allowed for the public pilot, matching its existing published
  output. Use `allowSourceMaps: false` and disable production source maps in the
  source build before onboarding private applications.
- Publishing fetches the latest blog `master` and retries normal pushes up to
  three times. It never force-pushes. This protects concurrent article commits.
- `publish` is restricted to the disposable GitHub Actions checkout; it refuses
  to reset a normal local checkout.
- To pause publication while retaining previews, set `SITE_SYNC_PUBLISH_ENABLED`
  to `false`. To pause everything, set `SITE_SYNC_ENABLED` to `false`. To pause only one app,
  set its `enabled` field to `false` in `.github/apps.json`.
- Pause before reverting an application synchronization commit; otherwise the
  collector will publish the newest available source build again.
- Workflow recreation or source history rewriting requires an explicit policy /
  state review. Old run numbers and divergent source history are rejected.
- Artifacts expire. If an uncollected build has expired, trigger a **new** source
  workflow run on `main` to generate a fresh artifact.

## Validation

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s .github/tests -v
```

The tests include tampered manifests, traversal / symlink rejection, unchanged
blog files, stale updates, pausing, failed builds and a real Git push conflict
with a concurrent article commit. They use temporary directories and local Git
repositories, not the public site. `check-static-sync.yml` runs them for changes
to this integration.
