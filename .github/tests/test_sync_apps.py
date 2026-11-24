import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/sync_apps.py"
spec = importlib.util.spec_from_file_location("sync_apps", SCRIPT)
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)

APP = {"enabled": True, "repository": "troyeagle/larp-clues-presentation", "branch": "main",
       "workflow": "publish-static.yml", "buildJob": "Build static application",
       "artifact": "site-clue", "destination": "clue", "allowSourceMaps": True}
BUILD = {"schema": 1, "app": "clue", "repository": APP["repository"], "sha": "a" * 40,
         "runId": "101", "runNumber": 2, "runAttempt": 1}


def payload():
    files = {"index.html": b'<script src="/clue/static/main.js"></script>',
             "static/main.js": b'console.log("clue");'}
    metadata = {**BUILD, "files": [{"path": path, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
                                  for path, data in files.items()]}
    files[sync.MANIFEST] = json.dumps(metadata).encode()
    return files


def archive(files):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as output:
        output.writestr("static/", b"")
        for name, data in files.items():
            output.writestr(name, data)
    return stream.getvalue()


class FakeGitHub:
    def __init__(self):
        self.run = {"id": 101, "run_number": 2, "run_attempt": 1, "head_sha": BUILD["sha"],
                    "head_branch": "main", "head_repository": {"full_name": APP["repository"]},
                    "event": "push", "status": "in_progress"}
        self.build_success = True
        self.comparison = "ahead"

    def json(self, path):
        if path.endswith("publish-static.yml"):
            return {"id": 9, "path": ".github/workflows/publish-static.yml"}
        if "/runs?" in path:
            return {"workflow_runs": [self.run]}
        if "/jobs?" in path:
            return {"jobs": [{"name": APP["buildJob"], "conclusion": "success" if self.build_success else "failure"},
                             {"name": "notify", "conclusion": None}]}
        if "/compare/" in path:
            return {"status": self.comparison}
        if "/artifacts?" in path:
            return {"artifacts": [{"id": 8, "name": APP["artifact"], "expired": False}]}
        raise AssertionError(path)

    def archive(self, repository, artifact):
        return sync.unpack_archive(archive(payload()))


class StaticSyncTests(unittest.TestCase):
    def check_documents(self, documents):
        files = {name: data.encode() for name, data in documents.items()}
        files[sync.MANIFEST] = json.dumps({**BUILD, 'files': [
            {'path': name, 'size': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
            for name, data in files.items()
        ]}).encode()
        return sync.validate_files(files, BUILD, APP)

    def test_nested_pages_support_directory_links_and_internal_parent_links(self):
        self.check_documents({'index.html': '<a href="decks/first/">Deck</a>',
                              'decks/first/index.html': '<a href="../../">Home</a><use href="#icon"/>'})

    def test_missing_asset_in_nested_html_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'missing static asset'):
            self.check_documents({'index.html': '<a href="deck/">Deck</a>',
                                  'deck/index.html': '<img src="missing.png">'})

    def test_decoded_parent_reference_cannot_escape_application(self):
        with self.assertRaisesRegex(ValueError, 'another site'):
            self.check_documents({'index.html': '<a href="deck/">Deck</a>',
                                  'deck/index.html': '<a href="..%2f..%2f_posts/article.html">Outside</a>'})

    def test_inline_script_strings_are_not_html_asset_references(self):
        self.check_documents({'index.html': '''<script>const example='<img src="not-a-resource.png">';</script><svg><use href="#icon"/></svg>'''})

    def test_base_tag_cannot_change_resource_resolution(self):
        with self.assertRaisesRegex(ValueError, 'base overrides'):
            self.check_documents({'index.html': '<base href="/another-app/">'})

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "blog"
        (self.root / ".github").mkdir(parents=True)
        self.config = {"schema": 1, "apps": {"clue": copy.deepcopy(APP)}}
        self.write_config()
        (self.root / sync.STATE_PATH).write_text('{"schema":1,"apps":{}}\n')
        for name in ["_posts", "_layouts", "countdown", "clue-viewer", "merger", "tragedy", "clue"]:
            (self.root / name).mkdir()
            (self.root / name / "keep.txt").write_text(name)
        self.prepared = self.base / "prepared"

    def write_config(self):
        (self.root / ".github/apps.json").write_text(json.dumps(self.config))

    def prepare(self, api=None):
        return sync.collect(self.root, self.prepared, api or FakeGitHub())

    def test_accepts_completed_build_while_notification_is_running(self):
        self.assertEqual(len(self.prepare()), 1)
        self.assertEqual((self.root / "clue/keep.txt").read_text(), "clue")

    def test_failed_build_does_not_replace_published_app(self):
        api = FakeGitHub()
        api.build_success = False
        self.assertEqual(self.prepare(api), [])
        self.assertEqual(sync.apply_updates(self.root, self.prepared), [])
        self.assertTrue((self.root / "clue/keep.txt").exists())

    def test_only_the_allowlisted_app_and_state_change(self):
        self.prepare()
        before = {path: path.read_bytes() for path in self.root.rglob("*") if path.is_file() and "clue" not in path.parts and path.name != "apps-state.json"}
        self.assertEqual(sync.apply_updates(self.root, self.prepared), ["clue"])
        self.assertFalse((self.root / "clue/keep.txt").exists())
        self.assertFalse((self.root / "clue/_site-sync.json").exists())
        self.assertEqual((self.root / "clue/static/main.js").read_bytes(), payload()["static/main.js"])
        for path, data in before.items():
            self.assertEqual(path.read_bytes(), data)
        self.assertEqual(sync.apply_updates(self.root, self.prepared), [])

    def test_tampered_payload_is_rejected_before_deleting_old_files(self):
        self.prepare()
        (self.prepared / "apps/clue/static/main.js").write_text("tampered")
        with self.assertRaisesRegex(ValueError, "mismatch"):
            sync.apply_updates(self.root, self.prepared)
        self.assertTrue((self.root / "clue/keep.txt").exists())

    def test_directory_traversal_and_symlinks_are_rejected(self):
        for path in ["../_posts/post.html", "/index.html", "static/../../index.html", "static\\main.js", ".env", "src/main.js"]:
            with self.subTest(path=path), self.assertRaises(ValueError):
                sync.unpack_archive(archive({path: b"bad"}))
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as output:
            info = zipfile.ZipInfo("index.html")
            info.create_system = 3
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            output.writestr(info, "../_posts")
        with self.assertRaisesRegex(ValueError, "symlink"):
            sync.unpack_archive(stream.getvalue())

    def test_archive_duplicates_are_rejected(self):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as output:
            output.writestr("index.html", "one")
            with self.assertWarns(UserWarning):
                output.writestr("index.html", "two")
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            sync.unpack_archive(stream.getvalue())

    def test_wrong_source_and_cross_app_asset_paths_are_rejected(self):
        files = payload()
        expected = {**BUILD, "sha": "b" * 40}
        with self.assertRaisesRegex(ValueError, "identity"):
            sync.validate_files(files, expected, APP)
        files["index.html"] = b'<script src="/countdown/main.js"></script>'
        metadata = json.loads(files[sync.MANIFEST])
        entry = next(entry for entry in metadata["files"] if entry["path"] == "index.html")
        entry.update(size=len(files["index.html"]), sha256=hashlib.sha256(files["index.html"]).hexdigest())
        files[sync.MANIFEST] = json.dumps(metadata).encode()
        with self.assertRaisesRegex(ValueError, "another site"):
            sync.validate_files(files, BUILD, APP)

    def test_source_history_rollback_is_rejected(self):
        api = FakeGitHub()
        api.comparison = "behind"
        with self.assertRaisesRegex(ValueError, "source branch"):
            self.prepare(api)
        self.assertTrue((self.root / "clue/keep.txt").exists())

    def test_pausing_an_app_blocks_an_already_prepared_update(self):
        self.prepare()
        self.config["apps"]["clue"]["enabled"] = False
        self.write_config()
        self.assertEqual(sync.apply_updates(self.root, self.prepared), [])
        self.assertTrue((self.root / "clue/keep.txt").exists())

    def test_onboarding_preview_can_collect_paused_app_without_publishing_it(self):
        self.config["apps"]["clue"]["enabled"] = False
        self.write_config()
        self.assertEqual(len(sync.collect(self.root, self.prepared, FakeGitHub(), include_disabled=True)), 1)
        self.assertEqual(sync.apply_updates(self.root, self.prepared), [])
        self.assertTrue((self.root / "clue/keep.txt").exists())

    def test_regular_collection_skips_paused_app(self):
        self.config["apps"]["clue"]["enabled"] = False
        self.write_config()
        self.assertEqual(self.prepare(), [])

    def test_symlink_destination_is_rejected(self):
        self.prepare()
        (self.root / "clue/keep.txt").unlink()
        (self.root / "clue").rmdir()
        (self.root / "clue").symlink_to(self.root / "_posts", target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "destination"):
            sync.apply_updates(self.root, self.prepared)
        self.assertEqual((self.root / "_posts/keep.txt").read_text(), "_posts")

    def test_publish_refuses_to_reset_a_local_checkout(self):
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "false"}):
            with self.assertRaisesRegex(ValueError, "disposable"):
                sync.publish(self.root, self.prepared, "test-token")

    def test_publish_preserves_a_concurrent_article_commit(self):
        def git(cwd, *args):
            return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)

        remote = self.base / "remote.git"
        git(self.base, "init", "--bare", "--initial-branch=master", str(remote))
        git(self.root, "init", "--initial-branch=master")
        git(self.root, "add", ".")
        git(self.root, "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", "Initial blog")
        git(self.root, "remote", "add", "origin", str(remote))
        git(self.root, "push", "-u", "origin", "master")
        self.prepare()
        writer = self.base / "writer"
        git(self.base, "clone", str(remote), str(writer))
        real_run = subprocess.run
        injected = False

        def concurrent_push(command, *args, **kwargs):
            nonlocal injected
            if command == ["git", "push", "origin", "HEAD:master"] and not injected:
                injected = True
                (writer / "_posts/new.md").write_text("Concurrent article")
                git(writer, "add", "_posts/new.md")
                git(writer, "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", "Publish article")
                git(writer, "push", "origin", "master")
            return real_run(command, *args, **kwargs)

        env = {"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": "troyeagle/troyeagle.github.io", "GITHUB_REF": "refs/heads/master"}
        with patch.dict(os.environ, env), patch.object(sync.subprocess, "run", side_effect=concurrent_push), patch.object(sync.time, "sleep"):
            sync.publish(self.root, self.prepared, "test-token")
        self.assertTrue(injected)
        self.assertEqual((self.root / "_posts/new.md").read_text(), "Concurrent article")
        names = git(self.root, "diff", "HEAD^", "HEAD", "--name-only").stdout.splitlines()
        self.assertTrue(all(name == sync.STATE_PATH or name.startswith("clue/") for name in names))


if __name__ == "__main__":
    unittest.main()
