"""The doctor's probe of the interpreter that runs the mechanism (agent-os#163): an interpreter
that cannot import what `agent_os.product` needs is reported with the module it lacks and the
exact command that repairs it, instead of a bare `No module named 'pydantic'` at the first command.

Real subprocesses, all of them Python: the suite's own interpreter, a venv built empty in
`tmp_path` (no network: `--without-pip`) and a path that does not exist. No backend is started.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

from agent_os import doctor
from agent_os.cli import AGENT_OS_DIR
from agent_os.product.tracker import mechanism_interpreter
from agent_os.product.tracker.mechanism_interpreter import (
    describe_mechanism_interpreter,
    probe_mechanism_interpreter,
    repair_command,
)


@pytest.fixture(autouse=True)
def reach_the_package_through_pythonpath(monkeypatch):
    # The probe inherits the environment, as a role's run does; the suite's own interpreter is
    # not guaranteed an editable install pointing at this checkout.
    monkeypatch.setenv("PYTHONPATH", str(AGENT_OS_DIR))
    monkeypatch.delenv("AGENT_OS_PYTHON", raising=False)


@pytest.fixture
def empty_virtualenv_python(tmp_path):
    venv = tmp_path / "host-root-venv"
    subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(venv)], check=True)
    return str(venv / "bin" / "python")


def test_an_interpreter_with_the_dependencies_passes():
    verdict = probe_mechanism_interpreter(sys.executable)
    assert verdict.ok, verdict
    assert sys.executable in describe_mechanism_interpreter(verdict)


def test_an_interpreter_without_the_dependencies_is_named_with_the_missing_module_and_the_repair(
    empty_virtualenv_python,
):
    verdict = probe_mechanism_interpreter(empty_virtualenv_python)

    assert not verdict.ok
    detail = describe_mechanism_interpreter(verdict)
    assert "No module named 'yaml'" in detail
    assert empty_virtualenv_python in detail
    assert f"`bash {AGENT_OS_DIR / 'bootstrap.sh'}`" in detail
    assert str(AGENT_OS_DIR / ".venv" / "bin" / "python") in detail
    assert ", not on a host's root .venv" in detail
    assert "\n" not in detail


def test_an_interpreter_that_does_not_exist_is_reported_not_raised(tmp_path):
    verdict = probe_mechanism_interpreter(str(tmp_path / "no" / "python"))

    assert not verdict.ok
    assert "cannot run it" in describe_mechanism_interpreter(verdict)


def test_a_host_named_interpreter_is_repaired_by_an_editable_install(monkeypatch):
    monkeypatch.setenv("AGENT_OS_PYTHON", "/opt/host/python")

    assert (
        repair_command("/opt/host/python") == f"/opt/host/python -m pip install -e {AGENT_OS_DIR}"
    )


def test_the_probe_covers_every_dependency_pyproject_declares():
    declared = {"yaml": "pyyaml", "pydantic": "pydantic", "jwt": "PyJWT", "cryptography": "PyJWT"}
    pyproject = (AGENT_OS_DIR / "pyproject.toml").read_text()

    assert set(declared) <= set(mechanism_interpreter.PROBED_MODULES)
    for distribution in set(declared.values()):
        assert f'"{distribution}' in pyproject


def test_the_doctor_check_is_the_probe_of_the_resolved_interpreter(
    monkeypatch, empty_virtualenv_python
):
    monkeypatch.setenv("AGENT_OS_PYTHON", empty_virtualenv_python)

    check = doctor.check_mechanism_interpreter()

    assert not check.ok
    assert check.name == doctor.MECHANISM_INTERPRETER_CHECK
    assert "pip install -e" in check.detail
    assert check.line().startswith("[FAIL] mechanism interpreter imports agent_os: ")
