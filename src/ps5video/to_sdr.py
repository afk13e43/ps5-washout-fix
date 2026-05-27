"""Path B: high-quality HDR -> SDR conversion using ffmpeg + libplacebo."""

from __future__ import annotations

from pathlib import Path

from rich.console import Console

from .ffmpeg_runner import get_duration_seconds, has_libplacebo, run_ffmpeg
from .presets import (
    SDR_AUDIO_BITRATE,
    SDR_CRF_QUALITY,
    SDR_CRF_QUICK,
    SDR_NPL,
    SDR_PRESET_QUALITY,
    SDR_PRESET_QUICK,
    SDR_TONEMAP,
)

console = Console()


def to_sdr(
    input_path: Path,
    output_path: Path,
    tonemap: str = SDR_TONEMAP,
    npl: int = SDR_NPL,
    crf: int | None = None,
    preset: str | None = None,
    quick: bool = False,
) -> None:
    """Tone-map PS5 HDR WebM to SDR BT.709 H.264 MP4 using libplacebo.

    libplacebo's `bt.2390` keeps far more colour than HandBrake's default Hable.
    Full Range input is handled correctly because we let libplacebo do the
    full PQ -> linear -> tone-map -> BT.709 pipeline.
    """
    if not has_libplacebo():
        raise RuntimeError(
            "Active ffmpeg lacks libplacebo support. Re-run scripts/setup_env.ps1 "
            "to overlay the gyan.dev build, or fall back to a zscale/tonemap path."
        )

    if output_path.exists():
        console.print(f"[yellow]Overwriting existing {output_path}[/yellow]")

    if crf is None:
        crf = SDR_CRF_QUICK if quick else SDR_CRF_QUALITY
    if preset is None:
        preset = SDR_PRESET_QUICK if quick else SDR_PRESET_QUALITY

    duration = get_duration_seconds(input_path)

    # libplacebo's peak_detect=true does per-scene HDR peak analysis,
    # which beats statically guessing the source peak luminance. `npl` is
    # kept as an arg for future use (e.g. forcing src_max via a future
    # libplacebo option) but is not passed today because ffmpeg's libplacebo
    # filter doesn't expose a source-peak override.
    _ = npl
    libplacebo_filter = (
        "libplacebo="
        f"tonemapping={tonemap}:"
        "colorspace=bt709:"
        "color_primaries=bt709:"
        "color_trc=bt709:"
        "format=yuv420p:"
        "range=tv:"
        "peak_detect=true"
    )

    args = [
        "-y",
        "-i", str(input_path),
        "-vf", libplacebo_filter,
        "-c:v", "libx264",
        "-crf", str(crf),
        "-preset", preset,
        "-pix_fmt", "yuv420p",
        "-color_primaries", "bt709",
        "-color_trc", "bt709",
        "-colorspace", "bt709",
        "-color_range", "tv",
        "-c:a", "aac",
        "-b:a", SDR_AUDIO_BITRATE,
        "-ac", "2",
        "-movflags", "+faststart",
        str(output_path),
    ]

    run_ffmpeg(args, total_seconds=duration, label=f"to-sdr {input_path.name}")
    console.print(f"[green]Wrote {output_path}[/green]")
