"""Install/uninstall a repository-local dispatcher without changing existing hooks."""
import argparse
import json
import os
from pathlib import Path
import re
import shlex
import subprocess

HOOKS = {"pre-commit", "prepare-commit-msg", "commit-msg", "post-commit", "pre-merge-commit",
         "pre-rebase", "pre-applypatch", "applypatch-msg", "post-applypatch", "post-checkout",
         "post-merge", "pre-push", "pre-receive", "update", "post-receive", "post-update",
         "push-to-checkout", "proc-receive", "reference-transaction", "post-rewrite",
         "pre-auto-gc", "post-index-change", "fsmonitor-watchman", "sendemail-validate"}
MARKER = "blog-local-commit-policy-v1"


def git(*args, check=True):
    return subprocess.run(["git", *args], check=check, capture_output=True, text=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["install", "status", "uninstall"], nargs="?", default="install")
    action = parser.parse_args().action
    root = Path(git("rev-parse", "--show-toplevel").stdout.strip()).resolve()
    remote = git("remote", "get-url", "origin", check=False).stdout.strip()
    if not re.fullmatch(r"(?:git@github\.com:|https://github\.com/|ssh://git@github\.com/)troyeagle/troyeagle\.github\.io(?:\.git)?/?", remote):
        raise ValueError("检查器只允许安装到 troyeagle/troyeagle.github.io。")
    common = Path(git("rev-parse", "--git-common-dir").stdout.strip())
    if not common.is_absolute():
        common = (root / common).resolve()
    local = common / "blog-commit-policy"
    state_file = local / "state.json"
    dispatch = local / "hooks"
    state = json.loads(state_file.read_text()) if state_file.exists() else None
    values = git("config", "--local", "--get-all", "core.hooksPath", check=False).stdout.splitlines()
    enabled = values == [str(dispatch)]
    if state and state.get("marker") != MARKER:
        raise ValueError("安装目录已有其他配置，拒绝覆盖。")
    if action == "status":
        print("本地提交检查：" + ("已启用" if state and enabled and dispatch.is_dir() else "未启用"))
        return
    if action == "uninstall":
        if not state:
            print("本地提交检查未安装。")
            return
        if not enabled:
            raise ValueError("钩子配置已被其他操作修改，拒绝覆盖。")
        git("config", "--local", "--unset-all", "core.hooksPath", check=False)
        for value in state["previous_local_values"]:
            git("config", "--local", "--add", "core.hooksPath", value)
        print("本地提交检查已停用，原钩子配置已恢复。")
        return
    if state and not enabled and values != state["previous_local_values"]:
        raise ValueError("钩子配置已变化，请先核对，拒绝覆盖。")
    if not state:
        if local.exists():
            raise ValueError("安装目录已存在且无有效记录，拒绝覆盖。")
        # Command-level tool overlays are not persistent repository hook settings.
        rows = git("config", "--show-scope", "--get-all", "core.hooksPath", check=False).stdout.splitlines()
        persisted = [line.split("\t", 1)[1] for line in rows
                     if "\t" in line and not line.startswith("command\t")]
        previous = persisted[-1] if persisted else str(common / "hooks")
        if git("config", "--worktree", "--get-all", "core.hooksPath", check=False).stdout.splitlines() and git("config", "--get", "extensions.worktreeConfig", check=False).stdout.strip() == "true":
            raise ValueError("检测到单独工作树钩子配置，请先核对，拒绝覆盖。")
        state = {"marker": MARKER, "previous_hooks_dir": previous, "previous_local_values": values}
        local.mkdir(mode=0o700)
        state_file.write_text(json.dumps(state, indent=2) + "\n")
        state_file.chmod(0o600)
    previous = Path(state["previous_hooks_dir"]).expanduser()
    names = HOOKS | ({p.name for p in previous.iterdir() if p.is_file() and not p.name.startswith(".") and not p.name.endswith(".sample")} if previous.is_dir() else set())
    dispatch.mkdir(exist_ok=True)
    runner = root / ".githooks/runner.py"
    for name in names:
        if not re.fullmatch(r"[a-z0-9-]+", name):
            continue
        path = dispatch / name
        if name in {"pre-commit", "commit-msg"}:
            body = "exec python3 " + shlex.quote(str(runner)) + " " + shlex.quote(str(state_file)) + " " + shlex.quote(name) + ' "$@"\n'
        else:
            original = shlex.quote(str(previous / name))
            body = "if [ -x " + original + " ]; then\n  exec " + original + ' "$@"\nfi\nexit 0\n'
        path.write_text("#!/bin/sh\n" + body)
        path.chmod(0o755)
    git("config", "--local", "core.hooksPath", str(dispatch))
    print("博客本地提交检查已安装；原钩子保留并串联执行。")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        raise SystemExit("安装失败：" + str(error))
