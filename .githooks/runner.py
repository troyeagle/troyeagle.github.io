"""Chain original repository hooks and then run the blog's local policy."""
import json
import os
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode = True
import policy


def main():
    if len(sys.argv) < 3:
        return 2
    state_file, hook, *args = sys.argv[1:]
    state = json.loads(Path(state_file).read_text())
    previous = Path(state["previous_hooks_dir"]).expanduser() / hook
    if previous.is_file() and os.access(previous, os.X_OK):
        # Pass arguments, cwd and stdin through; preserve original hooks in place.
        result = subprocess.run([str(previous), *args])
        if result.returncode:
            return result.returncode
    if hook == "pre-commit":
        return policy.report(policy.check_identities() + policy.check_index())
    if hook == "commit-msg":
        if not args:
            return 2
        return policy.report(policy.check_identities() + policy.check_index() + policy.check_message(args[0]))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, subprocess.CalledProcessError):
        print("[本地提交检查] 检查器无法完成验证，请重新安装或检查 Git 状态。", file=sys.stderr)
        sys.exit(1)
