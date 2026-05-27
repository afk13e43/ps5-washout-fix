"""Typer CLI entry point for ps5video."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from . import __version__
from .ffmpeg_runner import FFmpegError, ffmpeg_path, ffprobe_path, has_libplacebo
from .probe import probe_file, render_probe
from .remux_hdr import remux_hdr
from .to_sdr import to_sdr

app = typer.Typer(
    add_completion=False,
    help=(
        "Fix washed-out PS5 4K HDR WebM recordings for YouTube and PC playback.\n\n"
        "Default convention: drop .webm files in ./src_input, outputs go to "
        "./src_output. Both directories are relative to the current working "
        "directory. You can still pass full paths anywhere."
    ),
    no_args_is_help=True,
)
console = Console()

# Convention: relative to cwd. User runs from project root.
INPUT_DIR = Path("src_input")
OUTPUT_DIR = Path("src_output")


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"ps5video {__version__}")
        console.print(f"  ffmpeg:  {ffmpeg_path()}")
        console.print(f"  ffprobe: {ffprobe_path()}")
        console.print(f"  libplacebo: {'yes' if has_libplacebo() else 'NO (to-sdr will fail)'}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False, "--version", callback=_version_callback, is_eager=True,
        help="Show version and ffmpeg backend, then exit.",
    ),
) -> None:
    """Run `ps5video <command> --help` for details on each subcommand."""


def _resolve_input(path: Path) -> Path:
    """Accept either an explicit path or a bare filename in ./src_input."""
    if path.exists():
        return path
    candidate = INPUT_DIR / path.name
    if candidate.exists():
        return candidate
    console.print(
        f"[red]Input not found: '{path}' (also checked '{candidate}')[/red]"
    )
    raise typer.Exit(2)


def _default_output(input_path: Path, suffix: str, ext: str) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return OUTPUT_DIR / f"{input_path.stem}{suffix}.{ext}"


@app.command("probe")
def probe_cmd(
    input: Path = typer.Argument(..., help="Filename in ./src_input or explicit path."),
) -> None:
    """Show stream metadata and warn if input doesn't look like a PS5 HDR capture."""
    src = _resolve_input(input)
    try:
        result = probe_file(src)
    except FFmpegError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    render_probe(result)


@app.command("remux-hdr")
def remux_hdr_cmd(
    input: Path = typer.Argument(..., help="Filename in ./src_input or explicit path."),
    output: Optional[Path] = typer.Option(
        None, "-o", "--output",
        help="Output .mkv path (default: ./src_output/<name>_hdr.mkv).",
    ),
) -> None:
    """Path A: preserve HDR, fix metadata + audio codec for YouTube upload."""
    src = _resolve_input(input)
    out = output or _default_output(src, "_hdr", "mkv")
    try:
        remux_hdr(src, out)
    except FFmpegError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)


@app.command("to-sdr")
def to_sdr_cmd(
    input: Path = typer.Argument(..., help="Filename in ./src_input or explicit path."),
    output: Optional[Path] = typer.Option(
        None, "-o", "--output",
        help="Output .mp4 path (default: ./src_output/<name>_sdr.mp4).",
    ),
    tonemap: str = typer.Option("bt.2390", "--tonemap", help="libplacebo tonemap algorithm."),
    npl: int = typer.Option(1000, "--npl", help="Nominal source peak luminance (nits)."),
    crf: Optional[int] = typer.Option(None, "--crf", help="x264 CRF (lower = higher quality)."),
    preset: Optional[str] = typer.Option(None, "--preset", help="x264 preset."),
    quick: bool = typer.Option(False, "--quick", help="Faster preset, slightly lower quality."),
) -> None:
    """Path B: libplacebo bt.2390 tone map -> H.264 SDR MP4 for PC / fallback YT."""
    src = _resolve_input(input)
    out = output or _default_output(src, "_sdr", "mp4")
    try:
        to_sdr(src, out, tonemap=tonemap, npl=npl, crf=crf, preset=preset, quick=quick)
    except (FFmpegError, RuntimeError) as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)


@app.command("both")
def both_cmd(
    input: Path = typer.Argument(..., help="Filename in ./src_input or explicit path."),
    quick: bool = typer.Option(False, "--quick"),
) -> None:
    """Produce both <name>_hdr.mkv and <name>_sdr.mp4 in ./src_output."""
    src = _resolve_input(input)
    hdr_out = _default_output(src, "_hdr", "mkv")
    sdr_out = _default_output(src, "_sdr", "mp4")
    try:
        remux_hdr(src, hdr_out)
        to_sdr(src, sdr_out, quick=quick)
    except (FFmpegError, RuntimeError) as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)


@app.command("batch")
def batch_cmd(
    folder: Optional[Path] = typer.Argument(
        None,
        help="Folder to scan for .webm (default: ./src_input).",
    ),
    mode: str = typer.Option("both", "--mode", help="remux-hdr | to-sdr | both"),
    quick: bool = typer.Option(False, "--quick"),
) -> None:
    """Process every .webm in a folder (defaults to ./src_input)."""
    if mode not in {"remux-hdr", "to-sdr", "both"}:
        console.print(f"[red]Unknown --mode {mode}[/red]")
        raise typer.Exit(2)
    target = folder or INPUT_DIR
    if not target.is_dir():
        console.print(f"[red]Folder not found: {target}[/red]")
        raise typer.Exit(2)
    files = sorted(target.glob("*.webm"))
    if not files:
        console.print(f"[yellow]No .webm files in {target}[/yellow]")
        raise typer.Exit(0)
    console.print(f"[cyan]Processing {len(files)} file(s) in {mode} mode[/cyan]")
    for f in files:
        console.print(f"\n[bold]== {f.name} ==[/bold]")
        try:
            if mode in {"remux-hdr", "both"}:
                remux_hdr(f, _default_output(f, "_hdr", "mkv"))
            if mode in {"to-sdr", "both"}:
                to_sdr(f, _default_output(f, "_sdr", "mp4"), quick=quick)
        except (FFmpegError, RuntimeError) as e:
            console.print(f"[red]Failed on {f.name}: {e}[/red]")


if __name__ == "__main__":
    app()
