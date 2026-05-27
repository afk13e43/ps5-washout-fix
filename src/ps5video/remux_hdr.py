"""Path A: HDR-preserving remux. WebM/VP9/Opus -> MKV/VP9/AAC with HDR10 tags."""

from __future__ import annotations

from pathlib import Path

from rich.console import Console

from .ffmpeg_runner import run_ffmpeg
from .presets import DEFAULT_CONTENT_LIGHT_LEVEL, DEFAULT_MASTERING_DISPLAY
from .probe import probe_file

console = Console()


def remux_hdr(input_path: Path, output_path: Path) -> None:
    """Remux a PS5 WebM capture into MKV, preserving the VP9 video stream and
    tagging it as HDR10 so YouTube recognises it.

    - Video: -c:v copy + vp9_metadata bsf to rewrite color tags inside the VP9
      bitstream (no re-encode).
    - Container color tags via -color_primaries / -color_trc / -colorspace.
    - Audio: Opus -> AAC 192k stereo (YouTube friendlier than Opus-in-MKV).
    - Mastering display + MaxCLL metadata written via stream metadata; some
      players/muxers may ignore these without a re-encode but YouTube reads
      them from the MKV color elements when present.
    """
    if output_path.exists():
        console.print(f"[yellow]Overwriting existing {output_path}[/yellow]")

    # Preserve the source's color_range tag - PS5 captures can be either tv
    # or pc depending on firmware/game; misreporting it causes worse washout.
    info = probe_file(input_path)
    src_range = info.color_range if info.color_range in {"tv", "pc"} else "tv"
    duration = info.duration_s

    args = [
        "-y",
        "-i", str(input_path),
        "-map", "0:v:0",
        "-map", "0:a:0?",
        "-c:v", "copy",
        "-bsf:v", f"vp9_metadata=color_space=bt2020:color_range={src_range}",
        "-color_primaries", "bt2020",
        "-color_trc", "smpte2084",
        "-colorspace", "bt2020nc",
        "-color_range", src_range,
        "-metadata:s:v:0", f"mastering_display_metadata={DEFAULT_MASTERING_DISPLAY}",
        "-metadata:s:v:0", f"content_light_level={DEFAULT_CONTENT_LIGHT_LEVEL}",
        "-c:a", "aac",
        "-b:a", "192k",
        "-ac", "2",
        str(output_path),
    ]

    run_ffmpeg(args, total_seconds=duration, label=f"remux-hdr {input_path.name}")
    console.print(f"[green]Wrote {output_path}[/green]")
