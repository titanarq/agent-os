"""The test manifest: what each test group verifies and which tests belong to it.

The configured path is one YAML file, or a folder read recursively (every `*.yaml`). In a folder
each file may carry `groups` and `integration` lists; `version`, `test_globs`, `always` and `exempt`
live only in the file named `settings.yaml` at the folder's root. Loading is strict: an unknown key
is a loud error, because a misspelt `covers` would silently select nothing.
"""

from __future__ import annotations

import pathlib
from collections.abc import Mapping

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError

SETTINGS_FILE_NAME = "settings.yaml"
DEFAULT_TEST_GLOBS = ("tests/**/test_*.py",)
_SETTINGS_KEYS = ("version", "test_globs", "always", "exempt")
_LISTED_KEYS = ("groups", "integration")


class ManifestError(Exception):
    """The manifest is there but is not valid: the message names the file and the fault."""


class ManifestNotFoundError(Exception):
    """The configured manifest path does not exist, so no verdict about it can be given."""


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Group(_Strict):
    id: str
    nodes: tuple[str, ...] = ()
    covers: tuple[str, ...] = ()
    tests: tuple[str, ...] = ()


class Integration(_Strict):
    id: str
    sides: tuple[str, ...]
    tests: tuple[str, ...] = ()


class Settings(_Strict):
    version: int = 1
    test_globs: tuple[str, ...] = DEFAULT_TEST_GLOBS
    always: tuple[str, ...] = ()
    exempt: tuple[str, ...] = ()


class Manifest(_Strict):
    settings: Settings = Settings()
    groups: tuple[Group, ...] = ()
    integration: tuple[Integration, ...] = ()
    # What the configured path is called in a message: the file, or the folder.
    label: str = "the manifest"


def _parse_mapping(name: str, text: str) -> dict:
    try:
        loaded = yaml.safe_load(text)
    except yaml.YAMLError as error:
        raise ManifestError(f"{name}: not valid YAML: {error}") from error
    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        raise ManifestError(f"{name}: the top level must be a mapping")
    return loaded


def _allowed_keys(name: str, is_folder: bool) -> tuple[str, ...]:
    if not is_folder or name == SETTINGS_FILE_NAME:
        return (*_SETTINGS_KEYS, *_LISTED_KEYS)
    return _LISTED_KEYS


def parse_manifest(documents: Mapping[str, str], *, is_folder: bool, label: str) -> Manifest:
    """`documents` maps a file's name (relative to the folder, or the file's own name) to its text."""
    settings_raw: dict = {}
    listed: dict[str, list] = {key: [] for key in _LISTED_KEYS}
    for name in sorted(documents):
        mapping = _parse_mapping(name, documents[name])
        allowed = _allowed_keys(name, is_folder)
        unknown = sorted(set(mapping) - set(allowed))
        if unknown:
            where = (
                f"only `{SETTINGS_FILE_NAME}` at the root of the folder may hold settings"
                if set(unknown) & set(_SETTINGS_KEYS) and is_folder
                else f"allowed keys: {', '.join(allowed)}"
            )
            raise ManifestError(f"{name}: unknown key {', '.join(unknown)} ({where})")
        for key in _LISTED_KEYS:
            if key in mapping:
                if not isinstance(mapping[key], list):
                    raise ManifestError(f"{name}: `{key}` must be a list")
                listed[key] += mapping[key]
        settings_raw.update({key: mapping[key] for key in _SETTINGS_KEYS if key in mapping})
    try:
        return Manifest(settings=settings_raw, label=label, **listed)
    except ValidationError as error:
        details = "; ".join(
            f"{'.'.join(str(part) for part in problem['loc'])}: {problem['msg']}"
            for problem in error.errors()
        )
        raise ManifestError(f"{label}: {details}") from error


def manifest_file_names(directory: pathlib.Path) -> list[str]:
    return sorted(path.relative_to(directory).as_posix() for path in directory.rglob("*.yaml"))


def load_manifest(repository_root: pathlib.Path, manifest_path: str) -> Manifest:
    location = repository_root / manifest_path
    if location.is_dir():
        documents = {
            name: (location / name).read_text(encoding="utf-8")
            for name in manifest_file_names(location)
        }
        return parse_manifest(documents, is_folder=True, label=manifest_path)
    if location.is_file():
        documents = {manifest_path: location.read_text(encoding="utf-8")}
        return parse_manifest(documents, is_folder=False, label=manifest_path)
    raise ManifestNotFoundError(
        f"the manifest {manifest_path!r} does not exist under {repository_root}; "
        "fix `project.test_selection.manifest` or create it"
    )
