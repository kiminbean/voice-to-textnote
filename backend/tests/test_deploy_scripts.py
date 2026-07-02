from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read_deploy_script(name: str) -> str:
    return (ROOT / "deploy" / name).read_text(encoding="utf-8")


def test_setup_ubuntu_uses_current_project_repository_and_path():
    script = read_deploy_script("setup-ubuntu.sh")

    assert 'PROJECT_DIR="${PROJECT_DIR:-$HOME/voice-to-textnote}"' in script
    assert (
        'REPO_URL="${REPO_URL:-https://github.com/kiminbean/voice-to-textnote.git}"'
        in script
    )
    assert 'git clone "$REPO_URL" "$PROJECT_DIR"' in script
    assert "kiminbean/my-project" not in script
    assert "$HOME/voice-textnote" not in script
