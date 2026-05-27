"""Detect whether an input file looks like a PS5 HDR capture."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from rich.console import Console
from rich.table import Table

from .ffmpeg_runner import probe_json
from .presets import PS5_EXPECTED

console = Console()


@dataclass
class ProbeResult:
    codec_name: str | None
    width: int | None
    height: int | None
    pix_fmt: str | None
    color_primaries: str | None
    color_transfer: str | None
    color_space: str | None
    color_range: str | None
    audio_codec: str | None
    duration_s: float | None

    @property
    def looks_like_ps5_hdr(self) -> bool:
        return (
            self.codec_name == PS5_EXPECTED["codec_name"]
            and self.color_primaries == PS5_EXPECTED["color_primaries"]
            and self.color_transfer == PS5_EXPECTED["color_transfer"]
        )


def probe_file(path: Path) -> ProbeResult:
    data = probe_json(path)
    streams = data.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), {})
    audio = next((s for s in streams if s.get("codec_type") == "audio"), {})
    fmt = data.get("format", {})
    duration = None
    if "duration" in fmt:
        try:
            duration = float(fmt["duration"])
        except ValueError:
            pass
    return ProbeResult(
        codec_name=video.get("codec_name"),
        width=video.get("width"),
        height=video.get("height"),
        pix_fmt=video.get("pix_fmt"),
        color_primaries=video.get("color_primaries"),
        color_transfer=video.get("color_transfer"),
        color_space=video.get("color_space"),
        color_range=video.get("color_range"),
        audio_codec=audio.get("codec_name"),
        duration_s=duration,
    )


def render_probe(result: ProbeResult) -> None:
    table = Table(title="Stream info", show_header=False, box=None)
    table.add_column("key", style="cyan")
    table.add_column("value")
    rows = [
        ("video codec", result.codec_name),
        ("resolution", f"{result.width}x{result.height}" if result.width else None),
        ("pix_fmt", result.pix_fmt),
        ("color_primaries", result.color_primaries),
        ("color_transfer", result.color_transfer),
        ("color_space", result.color_space),
        ("color_range", result.color_range),
        ("audio codec", result.audio_codec),
        ("duration (s)", f"{result.duration_s:.2f}" if result.duration_s else None),
    ]
    for k, v in rows:
        table.add_row(k, str(v) if v is not None else "[dim]<missing>[/dim]")
    console.print(table)

    if result.looks_like_ps5_hdr:
        console.print("[green]Looks like a PS5 HDR capture.[/green]")
    else:
        console.print(
            "[yellow]Warning: does not match expected PS5 HDR signature "
            f"({PS5_EXPECTED}). Conversion will still attempt to run.[/yellow]"
        )
