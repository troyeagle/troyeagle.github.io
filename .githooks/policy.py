"""Local commit checks for the blog; inspect the index, never unstaged files."""
from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
import subprocess
import sys

EXPECTED_NAME = "troyeagle"
EXPECTED_EMAIL = "troyeagle@qq.com"
BOT_TRAILER = "Co-authored-by: Bot <bot@anonymous.com>"

# Fingerprints identify the owner's previous identities without storing the old values.
OWNER_NAMES = frozenset({
    "44e2a79676a7fe89d286b847ecac0b8b1d7ac3ed7044f8efc02b568c67fb67fc",
    "5d0d2e3211b003ea08679bcab3f138ca8f096d56cd5041a728b0cc9c2b5565ab",
    "6530b9f128c99d76e1fa56f33cedc9713b8b5bf3d64a35cc41cd26031f73384d",
    "83fb4e1f33bcd188c38d9f957427812cf0097b6be62f58fecfe2af568d5d79dc",
    "8652ada62e62a082fda9af673b1c71caf5506658962af4e1614251593594899e",
    "a6793586935a005a5758555bb20f190d26d2411d836086d2e5c0f3e9868a925c",
    "b0b5f54b20114024d9a08e1ea68051fe795be045f5a83ce86cffd76d3bf56304",
    "d48ef48a73b7b703fa4b0d781467aa12af612e35ef000f088156e1b93925b451",
})
PRIVATE_EMAILS = frozenset({
    "3a9d4aaa688a8bc632c6ef79a3ff3ec18c21b58b870ac7946d2874da2022b7f4",
    "3be8e58d3d8c0d166c0f5549be948dba1f66deb49a636e5cdb13aa781636c9da",
    "815099aa8c6ef3b60fc2ea0912686d181591aa7baa9a00be03910881c813e8e4",
    "9b8005abca1ed26671757fc8fb659bb34be347706e179900d60e78360b100946",
})
USER_ROOT = "/" + "Users" + "/"
ACCOUNT_PATH = re.compile(re.escape(USER_ROOT) + r"([^/\s\\'\"`<>]+)")
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
IDENT = re.compile(r"(.*?) <([^<>]*)> \d+ [+-]\d{4}\s*$")
COAUTHOR = re.compile(r"Co-authored-by:\s*(.*?)\s*<([^<>]+)>\s*$", re.I)
AI_NAME = re.compile(r"\b(?:TRAE|ChatGPT|Codex|Claude|DeepSeek|Anthropic|OpenAI|Copilot|Cursor|Windsurf|Aider|Gemini|GPT|Qwen|Seed|Bot)\b|bot\]?$", re.I)
BINARY_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf", ".zip",
                   ".gz", ".mp3", ".mp4", ".wav", ".woff", ".woff2", ".ttf", ".eot"}


def fingerprint(value):
    return hashlib.sha256(value.strip().casefold().encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Violation:
    code: str
    location: str
    message: str


def git(*args):
    return subprocess.check_output(["git", *args], stderr=subprocess.DEVNULL)


def check_text(text, location):
    errors = []
    for number, line in enumerate(text.splitlines(), 1):
        if any(m[1] != "{youraccountname}" for m in ACCOUNT_PATH.finditer(line)):
            errors.append(Violation("account-path", f"{location}:{number}",
                                    "真实账户路径请改为占位符或相对路径。"))
        if any(fingerprint(m[0]) in PRIVATE_EMAILS for m in EMAIL.finditer(line)):
            errors.append(Violation("private-email", f"{location}:{number}",
                                    "出现已脱敏的个人邮箱；请删除或使用当前指定身份。"))
    return errors


def check_identity(value, role):
    match = IDENT.fullmatch(value)
    if not match:
        return [Violation("identity-format", role, "无法解析 Git 提交身份。")]
    name, email = match.groups()
    owner = (fingerprint(name) in OWNER_NAMES or fingerprint(email) in PRIVATE_EMAILS
             or email.casefold() == EXPECTED_EMAIL)
    if owner and (name, email) != (EXPECTED_NAME, EXPECTED_EMAIL):
        return [Violation("owner-identity", role,
                          f"本人的提交身份必须为 {EXPECTED_NAME} <{EXPECTED_EMAIL}>。")]
    return []


def check_identities():
    errors = []
    for role, variable in [("作者", "GIT_AUTHOR_IDENT"), ("提交者", "GIT_COMMITTER_IDENT")]:
        errors.extend(check_identity(git("var", variable).decode("utf-8"), role))
    return errors


def check_index():
    errors = []
    paths = git("diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z").split(b"\0")
    for raw_path in paths:
        if not raw_path:
            continue
        path = raw_path.decode("utf-8", "surrogateescape")
        # Read the staged mode/content. A symlink is inspected as text, never followed.
        entry = git("ls-files", "--stage", "-z", "--", path).split(b"\0")[0]
        mode = entry.split(b" ", 1)[0]
        if mode == b"160000" or (mode != b"120000" and Path(path).suffix.lower() in BINARY_SUFFIXES):
            continue
        data = git("show", ":" + path)
        if b"\0" in data:
            continue
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            continue
        errors.extend(check_text(text, path))
    return errors


def check_message(path):
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    comment = subprocess.run(["git", "config", "--get", "core.commentChar"],
                             capture_output=True, text=True).stdout.strip() or "#"
    if comment == "auto":
        comment = "#"
    lines = []
    for line in text.splitlines():
        if line.startswith(comment + " ------------------------ >8 ------------------------"):
            break
        if not line.startswith(comment):
            lines.append(line)
    # -m can keep '#' lines and scissors markers literally. Inspect raw privacy
    # content conservatively so comment-looking text cannot hide account data.
    errors = check_text(text, "提交信息")
    bot_count = 0
    for number, line in enumerate(lines, 1):
        if not line.lower().startswith("co-authored-by"):
            continue
        match = COAUTHOR.fullmatch(line)
        if not match:
            errors.append(Violation("coauthor-format", f"提交信息:{number}", "协作者尾注格式无效。"))
            continue
        name, email = match.groups()
        if AI_NAME.search(name) or email.casefold() == "bot@anonymous.com":
            if line != BOT_TRAILER:
                errors.append(Violation("ai-coauthor", f"提交信息:{number}", "AI 协作者只允许规定的匿名 Bot 尾注。"))
            else:
                bot_count += 1
    if bot_count > 1:
        errors.append(Violation("duplicate-ai-coauthor", "提交信息", "匿名 AI 尾注只能保留一条。"))
    return errors


def report(errors):
    for error in errors:
        # Never echo the matched account, old email or message/body line.
        print(f"[本地提交检查/{error.code}] {error.location}: {error.message}", file=sys.stderr)
    return 1 if errors else 0
