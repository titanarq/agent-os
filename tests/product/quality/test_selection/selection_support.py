import pathlib
import subprocess

SINGLE_MANIFEST = """\
version: 1
always: [tests/test_guard.py]
exempt: [docs/changelog/]
groups:
  - id: worker
    covers: [bin/worker.sh, lib/worker/]
    tests: [tests/test_worker.py]
  - id: prompts
    nodes: [uc-prompts]
    covers: [prompts/]
    tests: [tests/test_prompts.py]
integration:
  - id: worker-and-prompts
    sides: [worker, prompts]
    tests: [tests/test_worker_prompts.py]
"""


def git(repository: pathlib.Path, *arguments: str) -> None:
    subprocess.run(
        ["git", "-C", str(repository), "-c", "user.name=t", "-c", "user.email=t@t", *arguments],
        check=True,
        capture_output=True,
    )


def write_file(repository: pathlib.Path, path: str, text: str = "x\n") -> None:
    target = repository / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text)


def commit_all(repository: pathlib.Path, message: str = "change") -> None:
    git(repository, "add", "-A")
    git(repository, "commit", "-q", "-m", message)


def make_repository(tmp_path: pathlib.Path) -> pathlib.Path:
    """A repository whose `main` holds a manifest and every file it maps; HEAD is `feature`."""
    root = tmp_path / "repository"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    write_file(root, "manifest.yaml", SINGLE_MANIFEST)
    for path in (
        "bin/worker.sh",
        "lib/worker/a.py",
        "prompts/p.md",
        "tests/test_guard.py",
        "tests/test_worker.py",
        "tests/test_prompts.py",
        "tests/test_worker_prompts.py",
        "docs/changelog/n.md",
        "other.txt",
    ):
        write_file(root, path)
    commit_all(root, "base")
    git(root, "checkout", "-q", "-b", "feature")
    return root
