import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
import policy

SOURCE = Path(__file__).parent
BOT = "\n\n" + policy.BOT_TRAILER


def plain_env():
    env = {k: v for k, v in os.environ.items() if not k.startswith(
        ("GIT_CONFIG", "GIT_AUTHOR", "GIT_COMMITTER", "TRAE_GIT_ATTRIBUTION"))}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


class RulesTests(unittest.TestCase):
    def test_public_text_and_placeholder(self):
        text = "普通文章内容；文件大小 512 字节\n/Users/{youraccountname}/project\n"
        self.assertEqual(policy.check_text(text, "post.md"), [])

    def test_path_error_never_echoes_account_or_line(self):
        account = "fixture-account"
        text = policy.USER_ROOT + account + "/private-note"
        errors = policy.check_text(text, "note.md")
        self.assertEqual([x.code for x in errors], ["account-path"])
        self.assertNotIn(account, repr(errors))
        self.assertNotIn("private-note", repr(errors))

    def test_email_fingerprint_in_link_does_not_echo_address(self):
        address = "historical-owner@example.test"
        with patch.object(policy, "PRIVATE_EMAILS", {policy.fingerprint(address)}):
            errors = policy.check_text("https://example.test/?email=" + address, "note.md")
        self.assertEqual([x.code for x in errors], ["private-email"])
        self.assertNotIn(address, repr(errors))

    def test_owner_name_and_email_are_checked(self):
        self.assertEqual(policy.check_identity("troyeagle <troyeagle@qq.com> 1 +0800", "作者"), [])
        self.assertTrue(policy.check_identity("troyeagle <other@example.test> 1 +0800", "作者"))
        self.assertTrue(policy.check_identity("Other Name <troyeagle@qq.com> 1 +0800", "提交者"))

    def test_third_party_and_automatic_identities_are_retained(self):
        self.assertEqual(policy.check_identity("Other Author <other@example.test> 1 +0800", "作者"), [])
        self.assertEqual(policy.check_identity("GitHub <noreply@github.com> 1 +0800", "提交者"), [])


class HookTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="blog-local-policy-", dir="/private/tmp")
        self.root = Path(self.temp.name)
        self.env = plain_env()
        self.git("init", "-q")
        self.git("config", "user.name", "troyeagle")
        self.git("config", "user.email", "troyeagle@qq.com")
        self.git("remote", "add", "origin", "https://github.com/troyeagle/troyeagle.github.io.git")
        (self.root / ".githooks").mkdir()
        for name in ["policy.py", "runner.py", "install.py"]:
            shutil.copyfile(SOURCE / name, self.root / ".githooks" / name)

    def tearDown(self):
        self.temp.cleanup()

    def git(self, *args, check=True, env=None):
        return subprocess.run(["git", *args], cwd=self.root, env=env or self.env,
                              capture_output=True, text=True, check=check)

    def install(self, action="install", check=True):
        return subprocess.run([sys.executable, ".githooks/install.py", action],
                              cwd=self.root, env=self.env, capture_output=True, text=True, check=check)

    def stage(self, text, name="post.md"):
        (self.root / name).write_text(text)
        self.git("add", "--", name)

    def commit(self, message="Add post", *extra, env=None):
        return self.git("commit", "-m", message, *extra, check=False, env=env)

    def assert_no_commit(self):
        self.assertNotEqual(self.git("rev-parse", "--verify", "HEAD", check=False).returncode, 0)

    def test_bad_staged_path_is_rejected_even_when_worktree_is_cleaned(self):
        self.install()
        self.stage(policy.USER_ROOT + "fixture-account/private\n")
        (self.root / "post.md").write_text("safe unstaged replacement\n")
        result = self.commit()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("account-path", result.stderr)
        self.assertNotIn("fixture-account", result.stderr)
        self.assert_no_commit()

    def test_unstaged_path_does_not_block_safe_index(self):
        self.install()
        self.stage("safe staged text\n")
        (self.root / "post.md").write_text(policy.USER_ROOT + "fixture-account/private\n")
        result = self.commit()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.git("show", "HEAD:post.md").stdout, "safe staged text\n")

    def test_author_override_and_committer_mismatch_are_blocked(self):
        self.install()
        self.stage("safe\n")
        result = self.commit("Bad author", "--author=troyeagle <wrong@example.test>")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("owner-identity", result.stderr)
        self.assert_no_commit()
        self.git("config", "user.email", "wrong@example.test")
        result = self.commit()
        self.assertNotEqual(result.returncode, 0)
        self.assert_no_commit()

    def test_bad_ai_duplicate_and_malformed_trailers_are_blocked(self):
        self.install()
        self.stage("safe\n")
        for trailer in ["Co-authored-by: Example Bot <bot@example.test>",
                        policy.BOT_TRAILER + "\n" + policy.BOT_TRAILER,
                        "Co-authored-by: missing email"]:
            result = self.commit("Add post\n\n" + trailer)
            self.assertNotEqual(result.returncode, 0, trailer)
            self.assert_no_commit()

    def test_human_and_anonymous_ai_commits_both_pass(self):
        self.install()
        self.stage("普通文章内容和文件大小 512 字节\n")
        self.assertEqual(self.commit().returncode, 0)
        self.stage("/Users/{youraccountname}/project\n")
        result = self.commit("Add anonymous contribution" + BOT)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_message_comment_marker_cannot_hide_a_private_path(self):
        self.install()
        self.stage("safe\n")
        result = self.commit("# " + policy.USER_ROOT + "fixture-account/private")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("account-path", result.stderr)
        self.assert_no_commit()

    def test_binary_is_skipped_and_symlink_target_is_not_followed(self):
        self.install()
        (self.root / "image.png").write_bytes(b"\0" + policy.USER_ROOT.encode() + b"fixture-account")
        self.git("add", "image.png")
        self.assertEqual(self.commit().returncode, 0)
        (self.root / "linked.png").symlink_to(policy.USER_ROOT + "fixture-account/missing")
        self.git("add", "linked.png")
        result = self.commit()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("account-path", result.stderr)

    def test_original_hook_runs_in_place_and_uninstall_restores_settings(self):
        original = self.root / ".git/hooks/pre-commit"
        body = '#!/bin/sh\nprintf reached > "$(dirname "$0")/original-marker"\nexit 0\n'
        original.write_text(body)
        original.chmod(0o755)
        original_hash = hashlib.sha256(original.read_bytes()).hexdigest()
        self.install()
        self.install()  # Installation is idempotent.
        self.stage("safe\n")
        result = self.commit()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((original.parent / "original-marker").read_text(), "reached")
        self.assertEqual(hashlib.sha256(original.read_bytes()).hexdigest(), original_hash)
        self.install("uninstall")
        self.assertNotEqual(self.git("config", "--local", "--get", "core.hooksPath", check=False).returncode, 0)
        self.assertEqual(hashlib.sha256(original.read_bytes()).hexdigest(), original_hash)

    def test_original_commit_message_hook_is_checked_after_it_runs(self):
        original = self.root / ".git/hooks/commit-msg"
        original.write_text('#!/bin/sh\nprintf "\\nCo-authored-by: Example Bot <bot@example.test>\\n" >> "$1"\n')
        original.chmod(0o755)
        self.install()
        self.stage("safe\n")
        result = self.commit("Add post" + BOT)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ai-coauthor", result.stderr)
        self.assert_no_commit()

    def test_other_repository_is_refused(self):
        self.git("remote", "set-url", "origin", "https://github.com/troyeagle/ai-video-reverse.git")
        self.assertNotEqual(self.install(check=False).returncode, 0)
        self.assertFalse((self.root / ".git/blog-commit-policy").exists())

    def test_custom_hook_path_stdin_and_configuration_are_preserved(self):
        original_dir = self.root / ".git/custom-hooks"
        original_dir.mkdir()
        original = original_dir / "pre-push"
        original.write_text('#!/bin/sh\nprintf "%s|%s" "$1" "$(cat)"\n')
        original.chmod(0o755)
        self.git("config", "--local", "core.hooksPath", ".git/custom-hooks")
        self.install()
        dispatch = Path(self.git("config", "--local", "--get", "core.hooksPath").stdout.strip())
        result = subprocess.run([str(dispatch / "pre-push"), "origin", "unused"], cwd=self.root,
                                env=self.env, input="update data\n", text=True, capture_output=True)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "origin|update data")
        self.install("uninstall")
        self.assertEqual(self.git("config", "--local", "--get", "core.hooksPath").stdout.strip(), ".git/custom-hooks")

    def test_installer_does_not_overwrite_subsequent_user_configuration(self):
        self.install()
        self.git("config", "--local", "core.hooksPath", ".git/other-hooks")
        result = self.install("uninstall", check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.git("config", "--local", "--get", "core.hooksPath").stdout.strip(), ".git/other-hooks")

    def test_tool_managed_hook_overlay_still_delegates_to_local_policy(self):
        effective = subprocess.run(["git", "config", "--get", "core.hooksPath"], capture_output=True, text=True).stdout.strip()
        if not effective or "TRAE_GIT_ATTRIBUTION_HELPER" not in os.environ:
            self.skipTest("No tool-managed hook overlay in this test session")
        self.install()
        self.stage(policy.USER_ROOT + "fixture-account/private\n")
        result = self.commit("Managed rejection" + BOT, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("account-path", result.stderr)
        self.assert_no_commit()
        self.stage("safe\n")
        result = self.commit("Managed success" + BOT, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        attribution = Path(effective) / ".attribution"
        if attribution.exists() and attribution.read_text().strip() != "Bot <bot@anonymous.com>":
            # A stale tool session adds its noncompliant footer; the checker must reject it.
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("ai-coauthor", result.stderr)
            self.assert_no_commit()
            local_hooks = self.git("config", "--local", "--get", "core.hooksPath").stdout.strip()
            result = self.git("-c", "core.hooksPath=" + local_hooks, "commit", "-m", "Local checked commit" + BOT, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.git("log", "-1", "--format=%B").stdout.count(policy.BOT_TRAILER), 1)


if __name__ == "__main__":
    unittest.main()
