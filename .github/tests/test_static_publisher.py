import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/package-static.mjs"
SPEC = importlib.util.spec_from_file_location("publisher_receiver", SCRIPT.with_name("sync_apps.py"))
receiver = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(receiver)


@unittest.skipUnless(shutil.which("node"), "Node is required for the publisher protocol checks")
class PublisherProtocolTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.dist = self.root / "dist"
        (self.dist / "assets").mkdir(parents=True)
        (self.dist / "index.html").write_text('<script src="/clue-viewer/assets/app.js"></script>')
        (self.dist / "assets/app.js").write_text("console.log('static')")
        self.env = {**os.environ, "GITHUB_REPOSITORY": "troyeagle/clue-viewer",
                    "GITHUB_REF": "refs/heads/master", "GITHUB_SHA": "a" * 40,
                    "GITHUB_RUN_ID": "21", "GITHUB_RUN_NUMBER": "3", "GITHUB_RUN_ATTEMPT": "1"}

    def run_publisher(self, command="package", app="clue-viewer", env=None):
        return subprocess.run(["node", str(SCRIPT), command, app], cwd=self.root,
                              env=env or self.env, capture_output=True, text=True)

    def test_private_unicode_assets_match_the_receiver_protocol(self):
        (self.dist / "线索").mkdir()
        (self.dist / "线索/图.png").write_bytes(b"image data")
        result = self.run_publisher()
        self.assertEqual(result.returncode, 0, result.stderr)
        files = {p.relative_to(self.dist).as_posix(): p.read_bytes() for p in self.dist.rglob("*") if p.is_file()}
        expected = {"schema": 1, "app": "clue-viewer", "repository": self.env["GITHUB_REPOSITORY"],
                    "sha": self.env["GITHUB_SHA"], "runId": "21", "runNumber": 3, "runAttempt": 1}
        app = {"destination": "clue-viewer", "allowSourceMaps": False}
        metadata, _ = receiver.validate_files(files, expected, app)
        self.assertEqual(len(metadata["files"]), 3)

    def test_private_source_maps_are_rejected(self):
        (self.dist / "assets/app.js.map").write_text("{}")
        self.assertNotEqual(self.run_publisher().returncode, 0)
        self.assertFalse((self.dist / "_site-sync.json").exists())

    def test_fork_or_non_release_branch_cannot_package_a_release(self):
        for changes in [{"GITHUB_REPOSITORY": "someone/clue-viewer"}, {"GITHUB_REF": "refs/heads/feature"}]:
            with self.subTest(changes=changes):
                self.assertNotEqual(self.run_publisher(env={**self.env, **changes}).returncode, 0)

    def test_reserved_manifest_symlink_is_rejected(self):
        external = self.root / "outside.json"
        external.write_text("protected")
        (self.dist / "_site-sync.json").symlink_to(external)
        self.assertNotEqual(self.run_publisher().returncode, 0)
        self.assertEqual(external.read_text(), "protected")

    def test_symlink_output_root_is_rejected(self):
        self.dist.rename(self.root / "outside")
        self.dist.symlink_to(self.root / "outside", target_is_directory=True)
        self.assertNotEqual(self.run_publisher().returncode, 0)

    def test_profile_selects_the_existing_lockfile_and_commands(self):
        output = self.root / "outputs"
        env = {**self.env, "GITHUB_REPOSITORY": "troyeagle/larp-countdown", "GITHUB_OUTPUT": str(output)}
        result = self.run_publisher("profile", "countdown", env)
        self.assertEqual(result.returncode, 0, result.stderr)
        values = dict(line.split("=", 1) for line in output.read_text().splitlines())
        self.assertEqual(values["manager"], "yarn")
        self.assertEqual(values["lockfile"], "yarn.lock")
        self.assertIn("--frozen-lockfile", values["install"])

    def test_packaging_twice_keeps_the_same_file_list(self):
        self.assertEqual(self.run_publisher().returncode, 0)
        first = json.loads((self.dist / "_site-sync.json").read_text())
        self.assertEqual(self.run_publisher().returncode, 0)
        second = json.loads((self.dist / "_site-sync.json").read_text())
        self.assertEqual(first, second)

    def test_python_projects_use_no_dependency_lockfile_or_install(self):
        for app in ['ai-video-reverse', 'expedition-alfonso-showcase']:
            with self.subTest(app=app):
                output = self.root / (app + '-outputs')
                env = {**self.env, 'GITHUB_REPOSITORY': 'troyeagle/' + app, 'GITHUB_OUTPUT': str(output)}
                result = self.run_publisher('profile', app, env)
                self.assertEqual(result.returncode, 0, result.stderr)
                values = dict(line.split('=', 1) for line in output.read_text().splitlines())
                self.assertEqual(values['manager'], 'python')
                self.assertEqual(values['lockfile'], '')
                self.assertEqual(values['install'], 'true')
                self.assertEqual(values['release_ref'], 'refs/heads/main')

    def test_new_projects_package_nested_html_under_their_own_prefix(self):
        for app in ['ai-video-reverse', 'expedition-alfonso-showcase']:
            with self.subTest(app=app):
                (self.dist / 'index.html').write_text('<a href="deck/">Open</a>')
                (self.dist / 'deck').mkdir(exist_ok=True)
                (self.dist / 'deck/index.html').write_text('<a href="../">Home</a>')
                env = {**self.env, 'GITHUB_REPOSITORY': 'troyeagle/' + app, 'GITHUB_REF': 'refs/heads/main'}
                result = self.run_publisher('package', app, env)
                self.assertEqual(result.returncode, 0, result.stderr)
                files = {p.relative_to(self.dist).as_posix(): p.read_bytes() for p in self.dist.rglob('*') if p.is_file()}
                expected = {'schema': 1, 'app': app, 'repository': env['GITHUB_REPOSITORY'],
                            'sha': env['GITHUB_SHA'], 'runId': '21', 'runNumber': 3, 'runAttempt': 1}
                receiver.validate_files(files, expected, {'destination': app, 'allowSourceMaps': False})
