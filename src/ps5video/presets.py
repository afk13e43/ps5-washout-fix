"""Constants and defaults for the two conversion paths."""

# Expected PS5 capture signature (used by probe.py)
PS5_EXPECTED = {
    "codec_name": "vp9",
    "color_primaries": "bt2020",
    "color_transfer": "smpte2084",
    "color_space": "bt2020nc",
}

# HDR10 mastering display metadata - P3-D65 primaries @ 1000 nits peak.
# PS5 doesn't write side_data into its captures, so this is a sensible default
# matching how most PS5 games are mastered.
# Format: G(x,y)B(x,y)R(x,y)WP(x,y)L(max,min)  - chromaticity * 50000, lum * 10000
DEFAULT_MASTERING_DISPLAY = (
    "G(13250,34500)B(7500,3000)R(34000,16000)WP(15635,16450)L(10000000,1)"
)
# MaxCLL, MaxFALL (cd/m^2)
DEFAULT_CONTENT_LIGHT_LEVEL = "1000,400"

# Path B (libplacebo SDR) defaults
SDR_TONEMAP = "bt.2390"        # ITU standard, best color retention
SDR_NPL = 1000                  # nominal peak luminance of source (nits)
SDR_CRF_QUALITY = 18            # x264 CRF for --quality preset
SDR_CRF_QUICK = 20              # x264 CRF for --quick preset
SDR_PRESET_QUALITY = "slow"
SDR_PRESET_QUICK = "medium"
SDR_AUDIO_BITRATE = "192k"
