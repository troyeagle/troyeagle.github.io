# Static application synchronization

Applications are `larp-clues-presentation` → `/clue/`, `larp-countdown` →
`/countdown/`, `clue-viewer` → `/clue-viewer/`, `image-merger-fe` → `/merger/`,
`ai-video-reverse` → `/ai-video-reverse/` and `expedition-alfonso-showcase` →
`/expedition-alfonso-showcase/`.
Jekyll, Hux templates, article files and all other application directories keep
their existing layout. Source code continues to live in its own repository.

## Workflow

1. Each source workflow tests and builds on its configured release branch.
   The shared-workflow callers use `build-static-app.yml` pinned to a full commit
   SHA, with `publisher_ref` pointing to the same revision. The existing clue
   workflow is unchanged.
2. It uploads `site-<app>`, including `_site-sync.json` with the source SHA,
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

Current authentication uses fine-grained PATs. A GitHub App is an optional
alternative, installed only on the six configured sources and the blog. Give the installation
`Contents: read/write` and `Actions: read`. Store:

| Blog setting | Value |
| --- | --- |
| Repository variable `SITE_SYNC_APP_ID` | App ID |
| Repository secret `SITE_SYNC_APP_PRIVATE_KEY` | App private key |

The collector requests an installation token scoped to the source repository
with **Contents read, Actions read**. The publisher requests a different token
scoped to **the blog only, Contents write**. The private key is stored only in
the blog repository, and source build jobs never receive it.

The same two fine-grained personal access tokens are stored only in the blog:

| Blog secret | Repository scope | Permissions |
| --- | --- | --- |
| `SOURCE_ARTIFACTS_TOKEN` | All six configured source repositories | Contents read, Actions read |
| `BLOG_PUBLISH_TOKEN` | `troyeagle.github.io` | Contents write |

For immediate notifications, create a separate fine-grained token scoped only
to **troyeagle.github.io, Actions write**, and store it as `BLOG_DISPATCH_TOKEN`
in each source repository that needs immediate notifications. This token cannot write blog contents. The
notification job is separate from the job executing application code.
The same notification token can be reused as a repository secret in each source;
repository secrets on personal accounts are not automatically shared. Never
distribute the blog Contents-write token to source repositories.

Use Actions secrets; do not place keys or tokens in files or chat messages.
Fine-grained PATs expire and require renewal. GitHub App installation tokens
are generated per job and automatically revoked by the official action.

## Onboard a source application

1. Land the receiver on blog `master`; land the source workflow on source `main`.
2. Configure the credentials above. Keep automatic collection disabled while
   the workflows and credentials are being installed.
3. Set the blog repository variable `SITE_SYNC_ENABLED` to `true`. Keep
   `SITE_SYNC_PUBLISH_ENABLED` unset or `false`. Collection and validation can
   run, but every publishing job is skipped until the second flag is enabled.
4. Run **Build static application** on the source release branch if no artifact is ready.
5. Run **Sync static applications** in the blog with `dry_run: true` (the default).
   Inspect its summary and the `prepared-static-updates` artifact. No write
   credential is generated and no commit is made during this run.
6. After reviewing the preview, set `SITE_SYNC_PUBLISH_ENABLED` to `true`, then
   run it again with `dry_run: false` to publish. Verify the resulting commit
   touches only the configured app directories and `.github/apps-state.json`,
   then check the normal GitHub Pages deployment and app URLs.
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
- New applications start with `enabled: false`. To preview them without changing
  the global publication flag, dispatch with both `dry_run: true` and
  `include_disabled: true`. Only a dry run can opt into collecting disabled apps;
  publication also independently skips disabled entries.
- Failed builds are skipped. Invalid downloaded artifacts fail validation
  before any published directory is replaced.
- Every file must be listed in the manifest. Symlinks, special files, hidden
  paths, source directories and traversal paths are rejected. Output size and
  entry count are bounded. All HTML files, including nested deck pages, must resolve local assets and directory links inside the app directory. Real HTML attributes are parsed; inline JavaScript strings are not treated as asset references.
- Source maps are allowed for the two public React apps. Both private Vite apps
  explicitly disable source maps, and their receiver policies reject them.
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
  workflow run on its configured release branch to generate a fresh artifact.

## Validation

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s .github/tests -v
```

The tests include publisher/receiver protocol compatibility, private source map
rejection, trusted repository/branch checks, tampered manifests, traversal /
symlink rejection, paused-app previews, unchanged blog files, stale updates,
failed builds and a real Git push conflict
with a concurrent article commit. They use temporary directories and local Git
repositories, not the public site. `check-static-sync.yml` runs them for changes
to this integration.

## Standalone HTML profiles

The two new sources use Python 3.12 standard-library builders and checks. Node 22
is used only for the shared manifest packager; dependency install and package
manager caches are skipped for these profiles. Existing source callers remain
pinned to their existing publisher revisions.

`ai-video-reverse/.github/static-pages.json` is an explicit public case registry.
Its builder exports a directory index and `<case-id>/index.html`, rebuilds and
validates the full slide/transcript data, and marks narration as local-only in
published decks. Media, reference frames, editable templates and working records
are not copied into releases.

`expedition-alfonso-showcase` is its own GitHub repository despite its nested local
checkout under `flight-price-watch`. Its builder retains the current host bridge,
embeds the exact scene, and exports only `index.html` and `LICENSE.txt`. Evidence
screenshots and original source snapshots are not part of the payload.

See each source's `.github/STATIC_PUBLISH.md` and the root `MAINTENANCE.md` for
commands, URLs, notification-secret configuration and recovery. The read-only
`SOURCE_ARTIFACTS_TOKEN` cannot dispatch workflows; immediate notifications need
the separately scoped `BLOG_DISPATCH_TOKEN`, with scheduled collection as fallback.
