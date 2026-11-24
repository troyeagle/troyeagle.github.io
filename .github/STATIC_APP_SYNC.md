# Static application synchronization and private-source fallback

Public projects deploy their own GitHub project Pages: `larp-clues-presentation`,
`larp-countdown`, `ai-video-reverse`, and `expedition-alfonso-showcase`. Their former
blog directories retain `remark.md` with source and destination links. The current
active blog applications are the private sources `clue-viewer` → `/clue-viewer/`
and `image-merger-fe` → `/merger/`. Hux layouts, posts and the unmapped `tragedy/`
application retain their existing structure.

## Deliberately retained fallback

The trusted registry keeps all six destination profiles. Public profiles are
paused (`enabled: false`) and select `publish-to-blog.yml`; source repositories
retain that workflow with `if: vars.SITE_PUBLISH_MODE == 'blog'`. Their default
project Pages workflow uses the opposite condition and refuses private-source
execution. An unset mode means public project Pages, never automatic fallback.

Keeping the fallback is intentional: a repository may later need to become
private. Review the output, select blog mode, extend the blog's source-read scope,
run a successful source fallback build, preview with `dry_run` and
`include_disabled`, then enable the destination and publish. The verified payload
replaces the migration remark only after explicit activation. Return to project
Pages by pausing the blog profile first, deploying the public source, and restoring
the remark. Paths for the clue/countdown project sites differ from blog fallback
paths; the pinned packager selects the correct legacy PUBLIC_URL.

## Publisher/receiver protocol

1. Source fallback builds call `build-static-app.yml` at a full immutable SHA;
   `publisher_ref` must use the same revision. Python HTML builds use standard
   library checks; frontend projects use existing lockfiles and Node 22.
2. All fallback profiles disable source maps. Successful release-branch builds
   upload `site-<app>` with `_site-sync.json`, including source SHA, run identity
   and SHA-256 hashes. PR builds have no production artifact or notification.
3. A separate optional notification job dispatches blog synchronization. The
   schedule at minutes 17 and 47 and manual execution work without notification.
4. The blog accepts only configured workflow/branch/successful build jobs,
   verifies source ancestry, archive digest, manifest identity, every file hash,
   file types, count/size limits, symlinks and all HTML local references.
5. Publishing revalidates the entire prepared batch against current policies,
   skips paused entries, replaces only approved destination directories and
   commits state. Root main is fetched before normal pushes; retries do not
   force-push or overwrite concurrent posts. Publishing is restricted to the
   disposable Actions checkout, never a normal local workspace.

Default collection and installation-token generation read only enabled sources.
An explicit onboarding preview includes disabled profiles; its read credential
must cover those sources and source fallback workflows must already exist.
Coalesced synchronization runs always scan the configured active set.

## Credentials and visibility

`SOURCE_ARTIFACTS_TOKEN` remains in the blog only, Contents read/Actions read on
active private sources. `BLOG_PUBLISH_TOKEN` is blog-only Contents write and
triggers branch-based Pages; the default GITHUB_TOKEN would not trigger that
existing branch deployment. An optional GitHub App uses correspondingly scoped
installation tokens. `BLOG_DISPATCH_TOKEN` is source-side, blog-only Actions
write, and is never the contents-write token.

Source visibility is not output visibility. Private-source fallback still
publishes public HTML/JS/CSS/assets; approve the payload and exclude secrets,
internal references, raw media, editable templates and source maps. Video export
uses an explicit case registry and retains local-only narration behavior.

## Configuration and recovery

`apps.json` is the sole runtime trust policy; events cannot supply a repository,
path, command or URL. `apps-state.json` records active published versions. Pause
before reverting a deployment. Prefer a new source revert commit and build;
history rewriting needs explicit authorization and provenance reset/revalidation.
Artifacts expire after 14 days, so trigger a fresh fallback source run if needed.

The root MAINTENANCE.md and each source's STATIC_PUBLISH.md contain concrete
configuration links, mode switches and the approved ordering for private migration.
Do not remove inactive fallback workflows or profiles solely because a project
currently deploys independently.

## Validation

Run `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s .github/tests -v`.
Tests cover identity/hash validation, paths and symlinks, source maps, scoped reads,
paused fallback protection of migration remarks, stale plans, failed builds and
concurrent article pushes. check-static-sync.yml runs these checks on integration
changes. Agent attribution follows the root AGENTS.md anonymous co-author rule.
