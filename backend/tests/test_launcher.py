import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import run


def test_build_process_specs_uses_venv_python_and_project_directories(tmp_path: Path):
    root = tmp_path
    python_dir = root / ("Scripts" if os.name == "nt" else "bin")
    python_name = "python.exe" if os.name == "nt" else "python"
    python_path = root / ".venv" / python_dir.name / python_name
    python_path.parent.mkdir(parents=True)
    python_path.touch()
    (root / "backend").mkdir()
    (root / "frontend").mkdir()

    specs = run.build_process_specs(root)

    assert specs[0].cwd == root / "backend"
    assert specs[0].argv[:2] == (str(python_path), "-m")
    assert specs[0].argv[2] == "uvicorn"
    assert specs[1].cwd == root / "frontend"
    assert specs[1].argv[-2:] == ("run", "dev")


def test_check_environment_reports_missing_venv(tmp_path: Path, capsys):
    assert run.check_environment(tmp_path) is False
    assert ".venv" in capsys.readouterr().out
