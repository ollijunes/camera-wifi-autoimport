"""Check every reachable Git snapshot for private infrastructure and runtime files."""

import ipaddress
import re
import subprocess
import sys

PATTERNS = {
    "private network address": re.compile(
        rb"\b(?:10(?:\.[0-9]{1,3}){3}|192\.168(?:\.[0-9]{1,3}){2}|"
        rb"172\.(?:1[6-9]|2[0-9]|3[01])(?:\.[0-9]{1,3}){2}|"
        rb"100\.(?:6[4-9]|[7-9][0-9]|1[01][0-9]|12[0-7])(?:\.[0-9]{1,3}){2})\b"
    ),
    "personal home directory": re.compile(
        rb"(?:/" rb"Users/[^/\s\"'<>]+/|/" rb"home/[^/\s\"'<>]+/|[Cc]:\\Users\\[^\\\s\"'<>]+\\)"
    ),
}
PRIVATE_FILE = re.compile(
    r"(?i)(?:^|/)(?:\.env(?:\..*)?|\.key|config\.toml|state\.sqlite3(?:-.*)?|"
    r"[^/]+\.(?:key|pem|p12|jpg|jpeg|arw|nef|cr3|heic|mp4|sqlite3|db|log|af))$"
)


def git(*args):
    return subprocess.check_output(["git", *args])  # noqa: S603,S607 - fixed git commands only.


def detect(data):
    return [name for name, pattern in PATTERNS.items() if pattern.search(data)]


def self_test():
    cases = []
    for address in (0x0A000001, 0xC0A80001, 0xAC100001, 0xAC1F0001, 0x64400001, 0x647F0001):
        cases.append((str(ipaddress.IPv4Address(address)), "private network address"))
    for parts, sep in (
        (["", "Users", "fixtureperson", "photo"], "/"),
        (["", "home", "fixtureperson", "photo"], "/"),
        (["C:", "Users", "fixtureperson", "photo"], "\\"),
    ):
        cases.append((sep.join(parts), "personal home directory"))
    for content, expected in cases:
        if expected not in detect(content.encode()):
            raise RuntimeError("Privacy detector missed a synthetic canary.")
    for name in ("private.key", ".env", "config.toml", "photo.jpg", "state.sqlite3", "private.log"):
        if not PRIVATE_FILE.search(name):
            raise RuntimeError("Privacy detector missed a private filename canary.")
    if detect(b"https://immich.example.invalid and http://127.0.0.1:2283"):
        raise RuntimeError("Privacy detector rejected a permitted example.")
    print("Privacy detector: 16 synthetic canaries passed.")


def main():
    self_test()
    if sys.argv[1:] == ["--self-test"]:
        return 0
    commits = git("rev-list", "--all").decode().splitlines()
    seen = set()
    failures = 0
    for commit in commits:
        metadata = git("show", "-s", "--format=%an <%ae>%n%cn <%ce>%n%B", commit)
        for category in detect(metadata):
            print(f"FAIL: commit {commit[:12]}: {category}; value withheld")
            failures += 1
        for entry in git("ls-tree", "-r", "-z", commit).split(b"\0"):
            if not entry:
                continue
            descriptor, path = entry.split(b"\t", 1)
            _, kind, oid = descriptor.split()
            if kind != b"blob" or (oid, path) in seen:
                continue
            seen.add((oid, path))
            categories = detect(path) + detect(git("cat-file", "blob", oid.decode()))
            if PRIVATE_FILE.search(path.decode(errors="replace")):
                categories.append("private runtime/photo file")
            for category in categories:
                # A path can itself contain a secret; identify only its Git object.
                print(f"FAIL: object {oid.decode()[:12]}: {category}; value withheld")
                failures += 1
    print(
        f"Privacy history: {len(commits)} commits, {len(seen)} file versions, {failures} findings."
    )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
