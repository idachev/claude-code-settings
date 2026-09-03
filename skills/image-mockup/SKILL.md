---
name: image-mockup
description: Wrap a screenshot in a device mockup (MacBook-style frame) or add a soft drop shadow. Use when the user asks to "put the screenshot on a laptop", "add a drop shadow", "make the image look nicer", "mock up on a MacBook", or similar screenshot-polishing requests. Runs a local ImageMagick script — no network, no external services.
---

# Image Mockup

Polish a screenshot with a device frame or drop shadow using the bundled script.

## When to use

Trigger on requests like:
- "put this image on a laptop" / "mock it up on a MacBook"
- "add a drop shadow to X.png"
- "make the image look nicer for a slide"
- "put the screenshot in a device frame"

Skip if the user wants a 3D perspective render, a real photo composite, or a specific stock mockup — this skill produces a flat, clean vector-style mockup only.

## Prerequisite

ImageMagick must be installed. Version 7 is enough on its own (`magick` in `$PATH`); version 6 needs **both** `convert` and `identify`, because the script measures the input before drawing. On Debian/Ubuntu: `sudo apt install imagemagick`. The script exits with a clear message when neither form is available.

## Usage

The script lives at `scripts/image-mockup.sh` next to this SKILL.md. Resolve the path from this file rather than assuming a fixed home, because `$CLAUDE_CONFIG_DIR` can move the config directory:

```bash
SKILL_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/skills/image-mockup"
```

The examples below use `~/.claude/skills/image-mockup/`, which is correct when `$CLAUDE_CONFIG_DIR` is unset.

```bash
~/.claude/skills/image-mockup/scripts/image-mockup.sh [--style shadow|laptop] INPUT [OUTPUT]
```

Default style is `laptop`. Output defaults to `<input-dir>/<stem>-<style>.png` so the original is never overwritten.

### Common invocations

```bash
# MacBook mockup with shadow (default)
~/.claude/skills/image-mockup/scripts/image-mockup.sh images/shot.png

# Just a soft drop shadow
~/.claude/skills/image-mockup/scripts/image-mockup.sh --style shadow images/shot.png

# Custom output path
~/.claude/skills/image-mockup/scripts/image-mockup.sh images/shot.png /tmp/out.png

# Beefier shadow
~/.claude/skills/image-mockup/scripts/image-mockup.sh \
  --shadow-opacity 75 --shadow-blur 35 --shadow-y 30 images/shot.png
```

### All tunable parameters

Run with `--help` to see the full list. Summary:

| Flag | Default | Purpose |
|------|---------|---------|
| `--style` | `laptop` | `shadow` = just shadow; `laptop` = MacBook frame + shadow |
| `--bezel` | `18` | Bezel thickness around screen (px) |
| `--notch-w` / `--notch-h` | `180` / `14` | Camera notch dimensions |
| `--base-extra` | `90` | How much the base extends past the screen each side |
| `--base-h` | `18` | Height of the laptop base plate |
| `--round` | `16` | Screen corner radius |
| `--pad` | `80` | Canvas padding (room for shadow) |
| `--shadow-opacity` | `60` | 0–100 |
| `--shadow-blur` | `25` | Gaussian sigma |
| `--shadow-x` / `--shadow-y` | `35` / `40` | Shadow offset (biased right+bottom) |

## Workflow

1. Confirm the input file exists and is a PNG/JPEG.
2. Pick `--style` based on the user's request (default to `laptop` for "mockup" phrasing, `shadow` if they only asked for a shadow).
3. Run the script. Output path is printed to stdout.
4. Read the output file back with the Read tool so you can visually verify the result.
5. If the user wants tweaks, adjust the relevant flag and rerun — don't edit the script itself unless a new capability is needed.

## Batch mode

For applying to many images in a folder, loop in the shell:

```bash
for f in images/claude-code-*.png; do
  ~/.claude/skills/image-mockup/scripts/image-mockup.sh --style shadow "$f"
done
```

## Extending

If a new style is needed (e.g. `phone`, `browser-window`, `tilted-laptop` with `-distort Perspective`), add a new branch in the script alongside the existing `shadow`/`laptop` branches rather than creating a parallel script. Keep one entry point.
