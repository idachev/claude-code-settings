#!/bin/bash
# image-mockup.sh — wrap a screenshot in a device mockup with a soft drop shadow.
#
# Styles:
#   shadow   just add a soft drop shadow to the image (transparent bg).
#   laptop   wrap in a MacBook-style frame (notch, bezels, hinge, base) + shadow.
#
# Usage:
#   image-mockup.sh [--style shadow|laptop] [OPTIONS] INPUT [OUTPUT]
#
# If OUTPUT is omitted, writes alongside INPUT with suffix "-<style>.png".

set -euo pipefail

STYLE="laptop"
OUTPUT=""
# Laptop knobs
BEZEL=18
NOTCH_W=180
NOTCH_H=14
BASE_EXTRA=90
BASE_H=18
HINGE_H=6
ROUND=16
NOTCH_ROUND=8
PAD=80
# Shadow knobs (applies to both styles) — biased to right+bottom
SH_OPACITY=60
SH_BLUR=25
SH_X=35
SH_Y=40

usage() {
  sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'
  cat <<EOF

Options:
  --style STYLE           shadow | laptop (default: laptop)
  -o, --output FILE       output path (default: <input>-<style>.png)
  --bezel N               screen bezel thickness (default: $BEZEL)
  --notch-w N             notch width (default: $NOTCH_W)
  --notch-h N             notch drop height (default: $NOTCH_H)
  --base-extra N          base extension each side past screen (default: $BASE_EXTRA)
  --base-h N              base plate height (default: $BASE_H)
  --round N               screen corner radius (default: $ROUND)
  --pad N                 canvas padding for shadow (default: $PAD)
  --shadow-opacity N      shadow opacity 0-100 (default: $SH_OPACITY)
  --shadow-blur N         shadow blur sigma (default: $SH_BLUR)
  --shadow-x N            shadow x offset (default: $SH_X)
  --shadow-y N            shadow y offset (default: $SH_Y)
  -h, --help              show this help
EOF
}

# --- parse args ---
INPUT=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --style)          STYLE="$2"; shift 2 ;;
    -o|--output)      OUTPUT="$2"; shift 2 ;;
    --bezel)          BEZEL="$2"; shift 2 ;;
    --notch-w)        NOTCH_W="$2"; shift 2 ;;
    --notch-h)        NOTCH_H="$2"; shift 2 ;;
    --base-extra)     BASE_EXTRA="$2"; shift 2 ;;
    --base-h)         BASE_H="$2"; shift 2 ;;
    --round)          ROUND="$2"; shift 2 ;;
    --pad)            PAD="$2"; shift 2 ;;
    --shadow-opacity) SH_OPACITY="$2"; shift 2 ;;
    --shadow-blur)    SH_BLUR="$2"; shift 2 ;;
    --shadow-x)       SH_X="$2"; shift 2 ;;
    --shadow-y)       SH_Y="$2"; shift 2 ;;
    -h|--help)        usage; exit 0 ;;
    -*)               echo "unknown option: $1" >&2; usage; exit 2 ;;
    *)
      if [[ -z "$INPUT" ]]; then INPUT="$1"
      elif [[ -z "$OUTPUT" ]]; then OUTPUT="$1"
      else echo "unexpected arg: $1" >&2; exit 2; fi
      shift ;;
  esac
done

[[ -z "$INPUT" ]] && { usage; exit 2; }
[[ ! -f "$INPUT" ]] && { echo "input not found: $INPUT" >&2; exit 1; }
[[ "$STYLE" != "shadow" && "$STYLE" != "laptop" ]] && { echo "invalid --style: $STYLE" >&2; exit 2; }

# Resolve the ImageMagick binaries (bypass shell aliases if any).
# v7 ships one "magick" entry point; v6 ships separate "convert" and "identify".
# Both are arrays because the v7 form needs two words: magick identify.
if magick_bin="$(command -v magick 2>/dev/null)"; then
  CONVERT=("$magick_bin")
  IDENTIFY=("$magick_bin" identify)
elif convert_bin="$(command -v convert 2>/dev/null)" \
  && identify_bin="$(command -v identify 2>/dev/null)"; then
  CONVERT=("$convert_bin")
  IDENTIFY=("$identify_bin")
else
  echo "ImageMagick not found: need 'magick' (v7), or both 'convert' and 'identify' (v6)" >&2
  exit 1
fi

# Default output path
if [[ -z "$OUTPUT" ]]; then
  dir="$(dirname "$INPUT")"
  base="$(basename "$INPUT")"
  stem="${base%.*}"
  OUTPUT="${dir}/${stem}-${STYLE}.png"
fi

SW=$("${IDENTIFY[@]}" -format "%w" "$INPUT")
SH=$("${IDENTIFY[@]}" -format "%h" "$INPUT")

shadow_step() {
  # $1 = input, $2 = output
  "${CONVERT[@]}" "$1" \
    \( +clone -background black -shadow "${SH_OPACITY}x${SH_BLUR}+${SH_X}+${SH_Y}" \) \
    +swap -background none -layers merge +repage \
    "$2"
}

if [[ "$STYLE" == "shadow" ]]; then
  shadow_step "$INPUT" "$OUTPUT"
else
  # laptop
  SFW=$((SW + BEZEL*2))
  SFH=$((SH + BEZEL*2))
  BW=$((SFW + BASE_EXTRA*2))

  CANVAS_W=$((BW + PAD*2))
  CANVAS_H=$((NOTCH_H + SFH + HINGE_H + BASE_H + PAD*2))

  SCREEN_X=$((PAD + BASE_EXTRA))
  SCREEN_Y=$((PAD + NOTCH_H))
  NX1=$((SCREEN_X + SFW/2 - NOTCH_W/2))
  NX2=$((SCREEN_X + SFW/2 + NOTCH_W/2))
  NY1=$PAD
  NY2=$((PAD + NOTCH_H + NOTCH_ROUND))
  HINGE_Y=$((SCREEN_Y + SFH))
  BASE_Y=$((HINGE_Y + HINGE_H))
  BASE_X=$PAD

  TMP="$(mktemp --suffix=.png)"
  trap 'rm -f "$TMP"' EXIT

  "${CONVERT[@]}" -size ${CANVAS_W}x${CANVAS_H} xc:none \
    -fill "#0a0a0a" \
      -draw "roundrectangle ${NX1},${NY1} ${NX2},${NY2} ${NOTCH_ROUND},${NOTCH_ROUND}" \
    -fill "#0a0a0a" \
      -draw "roundrectangle ${SCREEN_X},${SCREEN_Y} $((SCREEN_X+SFW-1)),$((SCREEN_Y+SFH-1)) ${ROUND},${ROUND}" \
    "$INPUT" -geometry +$((SCREEN_X+BEZEL))+$((SCREEN_Y+BEZEL)) -composite \
    -fill "#5c5c5c" \
      -draw "rectangle ${BASE_X},${HINGE_Y} $((BASE_X+BW-1)),$((HINGE_Y+HINGE_H-1))" \
    -fill "#d8d8d8" \
      -draw "roundrectangle ${BASE_X},${BASE_Y} $((BASE_X+BW-1)),$((BASE_Y+BASE_H-1)) 6,6" \
    -fill "#9a9a9a" \
      -draw "rectangle ${BASE_X},${BASE_Y} $((BASE_X+BW-1)),$((BASE_Y+2))" \
    "$TMP"

  shadow_step "$TMP" "$OUTPUT"
fi

echo "wrote: $OUTPUT"
"${IDENTIFY[@]}" -format "  %wx%h  %b\n" "$OUTPUT"
