"""Protected Runtime Loader contract for the three-model evidence import."""

from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
LOADER_PATH = (
    REPOSITORY_ROOT / "scripts" / "deployment" / "import_team_integration_env.ps1"
)


def test_loader_declares_fail_closed_three_model_official_source_profile() -> None:
    script = LOADER_PATH.read_text(encoding="utf-8")

    assert "[switch]$LoadThreeModelOfficialSources" in script
    assert "Choose one official source loading profile." in script
    assert "-PreferProtectedRuntime" in script
    assert "$officialSourceProfile = 'THREE_MODEL'" in script
    for environment_key in (
        "BACKEND_AI_OFFICIAL_SOURCE_PATH_JAC104",
        "BACKEND_AI_OFFICIAL_SOURCE_PATH_IAC425",
        "BACKEND_AI_OFFICIAL_SOURCE_PATH_IAC606",
    ):
        assert environment_key in script


def test_loader_keeps_the_single_model_profile_backward_compatible() -> None:
    script = LOADER_PATH.read_text(encoding="utf-8")

    assert "[switch]$LoadOfficialSource" in script
    assert "$officialSourceProfile = 'SINGLE_MODEL'" in script
    assert "'BACKEND_AI_OFFICIAL_SOURCE_PATH'" in script
    assert "secret_values_printed = $false" in script
