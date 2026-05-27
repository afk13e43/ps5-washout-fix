"""Subprocess wrapper for ffmpeg / ffprobe with progress reporting."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Iterable

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

console = Console()


class FFmpegError(RuntimeError):
    pass


def _find_binary(name: str) -> str:
    """Locate ffmpeg/ffprobe. Prefer the one next to the running Python (conda env),
    then fall back to PATH."""
    exe = f"{name}.exe" if sys.platform == "win32" else name
    candidates = [
        Path(sys.prefix) / "Library" / "bin" / exe,   # conda env on Windows
        Path(sys.prefix) / "bin" / exe,                # conda env on POSIX
    ]
    for c in candidates:
        if c.is_file():
            return str(c)
    found = shutil.which(name)
    if found:
        return found
    raise FFmpegError(
        f"{name} not found. Run scripts/setup_env.ps1 or install ffmpeg into PATH."
    )


def ffmpeg_path() -> str:
    return _find_binary("ffmpeg")


def ffprobe_path() -> str:
    return _find_binary("ffprobe")


def probe_json(input_path: Path) -> dict:
    """Return ffprobe's JSON output for the given file."""
    cmd = [
        ffprobe_path(),
        "-v", "error",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(input_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise FFmpegError(f"ffprobe failed: {result.stderr.strip()}")
    return json.loads(result.stdout)


def get_duration_seconds(input_path: Path) -> float | None:
    """Best-effort total duration in seconds, for progress bar."""
    try:
        data = probe_json(input_path)
    except FFmpegError:
        return None
    fmt = data.get("format", {})
    if "duration" in fmt:
        try:
            return float(fmt["duration"])
        except ValueError:
            return None
    return None


def has_libplacebo() -> bool:
    """Check whether the resolved ffmpeg supports the libplacebo filter."""
    try:
        out = subprocess.run(
            [ffmpeg_path(), "-hide_banner", "-filters"],
            capture_output=True, text=True, check=True,
        )
    except (subprocess.CalledProcessError, FFmpegError):
        return False
    return "libplacebo" in out.stdout


def run_ffmpeg(args: Iterable[str], total_seconds: float | None, label: str) -> None:
    """Run ffmpeg with -progress pipe:1 and display a rich progress bar.

    `args` is everything that goes AFTER `ffmpeg` (no binary path, no -progress).
    The function appends `-progress pipe:1 -nostats` itself.
    """
    cmd = [
        ffmpeg_path(),
        "-hide_banner",
        "-loglevel", "warning",
        "-nostats",
        "-progress", "pipe:1",
        *args,
    ]

    columns = [
        TextColumn("[bold cyan]{task.description}"),
        BarColumn(),
        TextColumn("{task.percentage:>5.1f}%"),
        TextColumn("•"),
        TimeElapsedColumn(),
        TextColumn("•"),
        TimeRemainingColumn(),
    ]

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    progress_total = (total_seconds or 0) * 1_000_000  # ffmpeg reports microseconds
    with Progress(*columns, console=console, transient=False) as progress:
        task_id = progress.add_task(
            label,
            total=progress_total if progress_total > 0 else None,
        )
        assert process.stdout is not None
        for line in process.stdout:
            line = line.strip()
            if not line or "=" not in line:
                continue
            key, _, value = line.partition("=")
            if key == "out_time_us" or key == "out_time_ms":
                # NOTE: ffmpeg's `out_time_ms` is actually microseconds (legacy naming).
                try:
                    us = int(value)
                except ValueError:
                    continue
                if progress_total > 0:
                    progress.update(task_id, completed=min(us, progress_total))
            elif key == "progress" and value == "end":
                if progress_total > 0:
                    progress.update(task_id, completed=progress_total)

    stderr_output = process.stderr.read() if process.stderr else ""
    retcode = process.wait()
    if retcode != 0:
        raise FFmpegError(
            f"ffmpeg exited {retcode}.\nCommand: {' '.join(cmd)}\n\n{stderr_output}"
        )
    if stderr_output.strip():
        # Surface ffmpeg warnings (loglevel=warning) even on success
        console.print(f"[yellow]ffmpeg notes:[/yellow]\n{stderr_output.strip()}")
