"""The validator reviews the diff's code quality and says so in the prompt it is handed."""

from agent_os.cli import AGENT_OS_DIR

VALIDATOR_TEMPLATE = (AGENT_OS_DIR / "prompts" / "validator.md").read_text()


def test_the_validator_is_told_to_review_solid_names_and_comments():
    for requirement in ("SOLID", "self-explanatory names", "non-obvious why"):
        assert requirement in VALIDATOR_TEMPLATE


def test_a_quality_finding_requests_changes_like_a_missed_criterion():
    assert "requests changes exactly as a missed criterion does" in " ".join(
        VALIDATOR_TEMPLATE.split()
    )


def test_the_validator_names_the_deterministic_check_it_does_not_repeat():
    assert "agent-os-quality" in VALIDATOR_TEMPLATE
