"""One-click launcher for the AI Werewolf backend and frontend."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
from typing import Sequence


ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class ProcessSpec:
    name: str
    argv: tuple[str, ...]
    cwd: Path


def resolve_venv_python(root: Path = ROOT) -> Path:
    """Return the project's virtual-environment interpreter."""
    relative = Path("Scripts/python.exe") if os.name == "nt" else Path("bin/python")
    path = root / ".venv" / relative
    if not path.is_file():
        raise RuntimeError(
            f"找不到项目虚拟环境：{path}\n"
            "请先运行 setup.cmd 创建 .venv 并安装依赖。"
        )
    return path.resolve()


def resolve_npm() -> str:
    """Return the npm executable available on PATH."""
    command = "npm.cmd" if os.name == "nt" else "npm"
    path = shutil.which(command)
    if not path:
        raise RuntimeError("找不到 npm，请先安装 Node.js 并确保 npm 已加入 PATH。")
    return path


def build_process_specs(root: Path = ROOT) -> tuple[ProcessSpec, ProcessSpec]:
    """Build the backend and frontend child-process commands."""
    python = resolve_venv_python(root)
    npm = resolve_npm()
    backend = root / "backend"
    frontend = root / "frontend"
    if not backend.is_dir():
        raise RuntimeError(f"找不到后端目录：{backend}")
    if not frontend.is_dir():
        raise RuntimeError(f"找不到前端目录：{frontend}")

    return (
        ProcessSpec(
            name="backend",
            argv=(
                str(python),
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8000",
            ),
            cwd=backend,
        ),
        ProcessSpec(
            name="frontend",
            argv=(str(npm), "run", "dev"),
            cwd=frontend,
        ),
    )


def check_environment(root: Path = ROOT) -> bool:
    """Validate all paths needed by the launcher without spawning services."""
    try:
        specs = build_process_specs(root)
    except RuntimeError as exc:
        print(f"[ERROR] {exc}")
        return False

    print(f"[OK] Python: {specs[0].argv[0]}")
    print(f"[OK] Backend: {specs[0].cwd}")
    print(f"[OK] npm: {specs[1].argv[0]}")
    print(f"[OK] Frontend: {specs[1].cwd}")
    return True


def _stop_process(process: subprocess.Popen[object]) -> None:
    if process.poll() is not None:
        return

    try:
        if os.name == "nt":
            process.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            process.terminate()
        process.wait(timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        process.kill()
        process.wait()


def _start_process(spec: ProcessSpec) -> subprocess.Popen[object]:
    options: dict[str, object] = {"cwd": str(spec.cwd)}
    if os.name == "nt":
        options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    return subprocess.Popen(spec.argv, **options)


def run_services(specs: tuple[ProcessSpec, ProcessSpec]) -> int:
    """Start both services and supervise them until one exits or Ctrl+C is pressed."""
    processes: list[tuple[ProcessSpec, subprocess.Popen[object]]] = []
    try:
        for spec in specs:
            print(f"[START] {spec.name}: {' '.join(spec.argv)}")
            processes.append((spec, _start_process(spec)))

        print("\n服务已启动：")
        print("  后端：http://127.0.0.1:8000")
        print("  前端：http://localhost:3000")
        print("\n按 Ctrl+C 同时停止前后端。\n")

        while True:
            for spec, process in processes:
                exit_code = process.poll()
                if exit_code is not None:
                    print(f"[STOP] {spec.name} 已退出，代码：{exit_code}")
                    return exit_code if exit_code else 0
            time.sleep(0.25)
    except KeyboardInterrupt:
        print("\n正在停止前后端……")
        return 0
    except OSError as exc:
        print(f"[ERROR] 启动服务失败：{exc}")
        return 1
    finally:
        for _, process in reversed(processes):
            _stop_process(process)


def _reexec_with_venv(root: Path, argv: Sequence[str]) -> None:
    python = resolve_venv_python(root)
    current = Path(sys.executable).resolve()
    if current == python:
        return

    print(f"[INFO] 使用项目虚拟环境：{python}")
    os.execv(str(python), [str(python), str(Path(__file__).resolve()), *argv])


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="一键启动 AI 狼人杀前后端")
    parser.add_argument("--check", action="store_true", help="只检查启动环境，不启动服务")
    args = parser.parse_args(argv)

    try:
        _reexec_with_venv(ROOT, sys.argv[1:] if argv is None else argv)
    except RuntimeError as exc:
        print(f"[ERROR] {exc}")
        return 1

    if args.check:
        return 0 if check_environment(ROOT) else 1

    try:
        specs = build_process_specs(ROOT)
    except RuntimeError as exc:
        print(f"[ERROR] {exc}")
        return 1
    return run_services(specs)


if __name__ == "__main__":
    raise SystemExit(main())
