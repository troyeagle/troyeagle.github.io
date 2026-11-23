"""Collect verified static artifacts and publish only configured app directories."""

import argparse
import base64
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

DESTINATIONS = {"clue", "countdown", "clue-viewer", "merger"}
MANIFEST = "_site-sync.json"
STATE_PATH = ".github/apps-state.json"
MAX_BYTES = 256 * 1024 * 1024
MAX_FILES = 10000
EXTENSIONS = {".html", ".js", ".css", ".json", ".png", ".jpg", ".jpeg", ".gif",
              ".webp", ".ico", ".svg", ".txt", ".xml", ".woff", ".woff2", ".ttf", ".eot", ".map"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load_config(root):
    config = json.loads((root / ".github/apps.json").read_text())
    require(config.get("schema") == 1 and isinstance(config.get("apps"), dict), "Invalid app configuration")
    for name, app in config["apps"].items():
        require(type(app.get("enabled", True)) is bool, "Invalid app enabled flag")
        require(name in DESTINATIONS and app.get("destination") == name, "Destination is outside the app allowlist")
        require(re.fullmatch(r"troyeagle/[A-Za-z0-9_.-]+", app.get("repository", "")), "Invalid source repository")
        require(re.fullmatch(r"[A-Za-z0-9_.-]+", app.get("branch", "")), "Invalid source branch")
        require(re.fullmatch(r"[A-Za-z0-9_.-]+\.yml", app.get("workflow", "")), "Invalid source workflow")
    return config["apps"]


def load_state(root):
    path = root / STATE_PATH
    require(not path.is_symlink(), "State file must not be a symlink")
    state = json.loads(path.read_text()) if path.exists() else {"schema": 1, "apps": {}}
    require(state.get("schema") == 1 and isinstance(state.get("apps"), dict), "Invalid published state")
    return state


def safe_path(path, directory=False):
    require(isinstance(path, str) and path and not re.search(r"[\x00-\x1f\\]", path), "Invalid artifact path")
    parts = path.split("/")
    require(all(part and part not in {".", "..", "src", "node_modules"} and not part.startswith(".") for part in parts),
            "Artifact path escapes the static file allowlist")
    require(not PurePosixPath(path).is_absolute(), "Absolute artifact path")
    require(directory or path == MANIFEST or PurePosixPath(path).suffix.lower() in EXTENSIONS, "Unsupported static file type")
    return path


def identity(run, app_name, app):
    require(run.get("head_repository", {}).get("full_name") == app["repository"], "Wrong source repository")
    require(run.get("head_branch") == app["branch"] and run.get("event") in {"push", "workflow_dispatch"}, "Untrusted source event")
    require(re.fullmatch(r"[a-f0-9]{40}", run.get("head_sha", "")), "Invalid source SHA")
    for key in ("id", "run_number", "run_attempt"):
        require(type(run.get(key)) is int and run[key] > 0, "Invalid build identity")
    return {"schema": 1, "app": app_name, "repository": app["repository"], "sha": run["head_sha"],
            "runId": str(run["id"]), "runNumber": run["run_number"], "runAttempt": run["run_attempt"]}


def validate_files(files, expected, app):
    require(MANIFEST in files and len(files) <= MAX_FILES + 1, "Missing manifest or too many files")
    require(sum(len(value) for value in files.values()) <= MAX_BYTES, "Artifact is too large")
    metadata = json.loads(files[MANIFEST])
    require(all(metadata.get(key) == value for key, value in expected.items()), "Artifact build identity does not match GitHub")
    entries = metadata.get("files")
    require(isinstance(entries, list) and entries and len(entries) <= MAX_FILES, "Invalid file manifest")
    names = set()
    for entry in entries:
        path = safe_path(entry["path"])
        require(path != MANIFEST and path not in names, "Duplicate or reserved manifest path")
        require(app.get("allowSourceMaps", False) or not path.endswith(".map"), "Source maps are disabled for this app")
        require(path in files, "Manifest references a missing file")
        data = files[path]
        require(type(entry.get("size")) is int and len(data) == entry["size"], "Static file size mismatch")
        require(hashlib.sha256(data).hexdigest() == entry.get("sha256"), "Static file hash mismatch")
        names.add(path)
    require(set(files) == names | {MANIFEST} and "index.html" in names, "Unexpected files or missing index.html")
    prefix = f'/{app["destination"]}/'
    for url in re.findall(r'(?:src|href)=["\']([^"\']+)', files["index.html"].decode("utf-8")):
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme or parsed.netloc or not parsed.path:
            continue
        path = urllib.parse.unquote(parsed.path)
        if path.startswith("/"):
            require(path.startswith(prefix), "HTML references another site's directory")
            path = path[len(prefix):]
        require(safe_path(path) in names, "HTML references a missing static asset")
    canonical = json.dumps(sorted(entries, key=lambda entry: entry["path"]), sort_keys=True, separators=(",", ":")).encode()
    return metadata, hashlib.sha256(canonical).hexdigest()


def unpack_archive(data):
    require(len(data) <= MAX_BYTES, "Archive is too large")
    files = {}
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        require(len(archive.infolist()) <= MAX_FILES * 2, "Too many archive entries")
        total = 0
        for info in archive.infolist():
            path = safe_path(info.filename.rstrip("/"), directory=info.is_dir())
            mode = stat.S_IFMT(info.external_attr >> 16)
            require(mode in {0, stat.S_IFREG, stat.S_IFDIR}, "Archive contains a symlink or special file")
            if info.is_dir():
                continue
            require(path not in files, "Duplicate archive path")
            total += info.file_size
            require(total <= MAX_BYTES, "Expanded archive is too large")
            files[path] = archive.read(info)
    return files


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        return None


class GitHub:
    def __init__(self, token):
        require(token, "Configure SITE_SYNC_APP_ID/SITE_SYNC_APP_PRIVATE_KEY or SOURCE_ARTIFACTS_TOKEN")
        self.token = token

    def request(self, path):
        request = urllib.request.Request("https://api.github.com" + path, headers={
            "Authorization": "Bearer " + self.token, "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "troyeagle-static-sync"})
        try:
            return urllib.request.build_opener(NoRedirect()).open(request, timeout=60)
        except urllib.error.HTTPError as error:
            if error.code == 302:
                return error
            raise ValueError(f"GitHub API request failed (HTTP {error.code})") from None

    def json(self, path):
        with self.request(path) as response:
            require(response.status == 200, "Unexpected API redirect")
            return json.load(response)

    def archive(self, repository, artifact):
        with self.request(f'/repos/{repository}/actions/artifacts/{artifact["id"]}/zip') as response:
            require(response.status == 302, "Expected an artifact download redirect")
            url = response.headers["Location"]
        require(urllib.parse.urlsplit(url).scheme == "https", "Unsafe download redirect")
        # The signed storage URL receives no GitHub authentication header.
        with urllib.request.urlopen(url, timeout=60) as response:
            data = response.read(MAX_BYTES + 1)
        digest = artifact.get("digest")
        if digest:
            require(digest == "sha256:" + hashlib.sha256(data).hexdigest(), "GitHub artifact digest mismatch")
        return unpack_archive(data)


def collect(root, output, api):
    apps, state = load_config(root), load_state(root)
    require(not output.exists(), "Prepared output directory already exists")
    output.mkdir(parents=True)
    updates = []
    for name, app in apps.items():
        if not app.get("enabled", True):
            continue
        repository = app["repository"]
        workflow = f'/repos/{repository}/actions/workflows/{app["workflow"]}'
        details = api.json(workflow)
        require(details.get("path") == ".github/workflows/" + app["workflow"], "Unexpected workflow path")
        runs = api.json(workflow + f'/runs?branch={app["branch"]}&per_page=100')["workflow_runs"]
        previous = state["apps"].get(name, {})
        for run in sorted(runs, key=lambda run: run["run_number"], reverse=True):
            if run["run_number"] <= previous.get("runNumber", 0):
                continue
            if run.get("head_branch") != app["branch"] or run.get("event") not in {"push", "workflow_dispatch"}:
                continue
            jobs = api.json(f'/repos/{repository}/actions/runs/{run["id"]}/jobs?per_page=100')["jobs"]
            if not any(job["name"] == app["buildJob"] and job.get("conclusion") == "success" for job in jobs):
                continue
            expected = identity(run, name, app)
            # A completed build job can be accepted while the notification job is still running.
            comparison = api.json(f'/repos/{repository}/compare/{expected["sha"]}...{app["branch"]}')
            require(comparison["status"] in {"ahead", "identical"}, "Build is no longer on the source branch")
            if previous.get("sha"):
                comparison = api.json(f'/repos/{repository}/compare/{previous["sha"]}...{expected["sha"]}')
                require(comparison["status"] in {"ahead", "identical"}, "Refusing a source history rollback")
            artifacts = api.json(f'/repos/{repository}/actions/runs/{run["id"]}/artifacts?per_page=100')["artifacts"]
            artifacts = [item for item in artifacts if item["name"] == app["artifact"] and not item.get("expired")]
            if not artifacts:
                continue
            require(len(artifacts) == 1, "Ambiguous source artifact")
            artifact = artifacts[0]
            files = api.archive(repository, artifact)
            metadata, digest = validate_files(files, expected, app)
            target = output / "apps" / name
            for path, data in files.items():
                destination = target / path
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(data)
            updates.append({"app": name, "config": app, "identity": expected, "digest": digest,
                            "artifactId": artifact["id"], "workflowId": details["id"]})
            print(f'{name}: verified build {expected["runNumber"]} ({expected["sha"][:12]})')
            break
    (output / "plan.json").write_text(json.dumps({"schema": 1, "updates": updates}, indent=2) + "\n")
    return updates


def apply_updates(root, prepared):
    apps, state = load_config(root), load_state(root)
    plan = json.loads((prepared / "plan.json").read_text())
    require(plan.get("schema") == 1 and isinstance(plan.get("updates"), list), "Invalid synchronization plan")
    validated = []
    names = set()
    for update in plan["updates"]:
        name = update["app"]
        require(name in apps and name not in names, "Unknown or duplicated app")
        names.add(name)
        if not apps[name].get("enabled", True):
            continue
        require(update["config"] == apps[name], "Synchronization policy changed")
        expected = update["identity"]
        require(expected.get("app") == name and expected.get("repository") == apps[name]["repository"], "Wrong prepared source")
        previous = state["apps"].get(name, {})
        if expected["runNumber"] <= previous.get("runNumber", 0):
            continue
        require(not previous.get("workflowId") or previous["workflowId"] == update["workflowId"], "Source workflow identity changed")
        source = prepared / "apps" / name
        require(not source.is_symlink(), "Prepared app must not be a symlink")
        files = {}
        for path in source.rglob("*"):
            require(not path.is_symlink(), "Prepared payload contains a symlink")
            if path.is_file():
                relative = safe_path(path.relative_to(source).as_posix())
                require(path.stat().st_size <= MAX_BYTES, "Prepared file is too large")
                files[relative] = path.read_bytes()
        metadata, digest = validate_files(files, expected, apps[name])
        require(digest == update["digest"], "Prepared payload digest changed")
        target = root / apps[name]["destination"]
        require(not target.is_symlink() and target.resolve().parent == root.resolve(), "Unsafe destination directory")
        require(not target.exists() or target.is_dir(), "Destination is not a directory")
        validated.append((name, target, files, update))
    # Validate the entire batch before modifying any published directory.
    for name, target, files, update in validated:
        if target.exists():
            shutil.rmtree(target)
        for path, data in files.items():
            if path == MANIFEST:
                continue
            destination = target / path
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
        state["apps"][name] = {**update["identity"], "digest": update["digest"],
                              "artifactId": update["artifactId"], "workflowId": update["workflowId"]}
    if validated:
        (root / STATE_PATH).write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")
    return [name for name, *_ in validated]


def publish(root, prepared, token):
    require(os.environ.get("GITHUB_ACTIONS") == "true", "Publishing is restricted to the disposable GitHub Actions checkout")
    require(os.environ.get("GITHUB_REPOSITORY") == "troyeagle/troyeagle.github.io" and
            os.environ.get("GITHUB_REF") == "refs/heads/master", "Publishing must run on the blog master branch")
    require(token, "Configure a GitHub App or BLOG_PUBLISH_TOKEN; GITHUB_TOKEN will not trigger branch-based Pages builds")
    env = {**os.environ, "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "http.https://github.com/.extraheader",
           "GIT_CONFIG_VALUE_0": "AUTHORIZATION: basic " + base64.b64encode(("x-access-token:" + token).encode()).decode()}

    def git(*args, check=True):
        result = subprocess.run(["git", *args], cwd=root, env=env, capture_output=True, text=True)
        if check and result.returncode:
            raise ValueError("Git operation failed: " + args[0])
        return result

    require(not git("status", "--porcelain").stdout, "Publish checkout must be clean")
    for attempt in range(3):
        git("fetch", "origin", "master")
        git("reset", "--hard", "origin/master")
        changed = apply_updates(root, prepared)
        if not changed:
            print("No newer application builds to publish")
            return
        git("add", "--", STATE_PATH, *changed)
        paths = git("diff", "--cached", "--name-only", "-z").stdout.split("\0")
        require(all(not path or path == STATE_PATH or any(path.startswith(name + "/") for name in changed) for path in paths),
                "Staged changes include files outside configured app directories")
        git("-c", "user.name=Static application sync", "-c", "user.email=41898282+github-actions[bot]@users.noreply.github.com",
            "commit", "-m", "chore: sync static applications (" + ", ".join(changed) + ")")
        if not git("push", "origin", "HEAD:master", check=False).returncode:
            print("Published: " + ", ".join(changed))
            return
        time.sleep(attempt + 1)
    raise ValueError("Normal push failed after three retries; no force push was attempted")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["repositories", "prepare", "publish"])
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--prepared", type=Path)
    args = parser.parse_args()
    if args.command == "repositories":
        print(",".join(sorted({app["repository"].split("/", 1)[1] for app in load_config(args.root).values()})))
    elif args.command == "prepare":
        require(args.prepared is not None, "Specify --prepared")
        updates = collect(args.root, args.prepared, GitHub(os.environ.get("SOURCE_TOKEN")))
        if os.environ.get("GITHUB_OUTPUT"):
            with open(os.environ["GITHUB_OUTPUT"], "a") as output:
                output.write(f'changed={str(bool(updates)).lower()}\n')
        if os.environ.get("GITHUB_STEP_SUMMARY"):
            with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as summary:
                summary.write("## Static application sync\n\n")
                summary.write("\n".join(f'- {update["app"]}: `{update["identity"]["sha"]}` (build {update["identity"]["runNumber"]})' for update in updates) or "No new successful builds.")
                summary.write("\n")
    else:
        require(args.prepared is not None, "Specify --prepared")
        publish(args.root, args.prepared, os.environ.get("PUBLISH_TOKEN"))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, zipfile.BadZipFile) as error:
        print("Static sync failed: " + str(error), file=sys.stderr)
        sys.exit(1)
