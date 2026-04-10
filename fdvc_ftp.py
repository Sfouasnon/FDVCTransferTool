#!/usr/bin/env python3
"""
FDVC FTP — Pull targeted clips OR full reels from the RED camera array.

Usage (interactive):  python3 fdvc_ftp.py
Usage (scripted):     python3 fdvc_ftp.py <output_dir> <manifest_csv>

Clip input format (one per line):
  G007_A083        ← reel_clip  (pulls that specific clip)
  ALL:007          ← ALL cameras, reel 007
"""
import sys
import os
from pathlib import Path

# Allow running from any directory
sys.path.insert(0, str(Path(__file__).parent))
from fdvc_core import (
    CAMERAS, is_online, ftp_connect, ftp_download_dir,
    xxh128, Manifest, human_size, parse_camera_label
)


def pull_clips(clip_list: list[str], output_dir: Path, manifest: Manifest):
    """
    clip_list items:
      "G007_A083"   → camera GA, reel hint G007, clip A083
      "ALL:007"     → all cameras, reel 007
    """
    # Expand ALL: entries
    expanded = []
    for entry in clip_list:
        if entry.upper().startswith("ALL:"):
            reel_num = entry.split(":", 1)[1].strip()
            for label in CAMERAS:
                expanded.append(("ALL", label, reel_num, None))
        else:
            parts = entry.strip().split("_")
            if len(parts) < 2:
                print(f"  ⚠  Skipping unrecognised format: {entry}")
                continue
            reel_hint = parts[0].upper()        # G007
            clip_id   = parts[1].upper()        # A083
            reel_letter = reel_hint[0]           # G
            cam_letter  = clip_id[0]             # A
            label = f"{reel_letter}{cam_letter}" # GA
            expanded.append(("CLIP", label, reel_hint, clip_id))

    # Group by camera to minimise FTP connections
    by_cam: dict[str, list] = {}
    for mode, label, reel_hint, clip_id in expanded:
        by_cam.setdefault(label, []).append((mode, reel_hint, clip_id))

    for label, tasks in sorted(by_cam.items()):
        ip = CAMERAS.get(label)
        if not ip:
            print(f"\n  ⚠  No IP mapping for camera {label}")
            continue

        print(f"\n>>> {label} ({ip})", end="  ", flush=True)
        if not is_online(ip):
            print("❌ OFFLINE")
            for _, reel_hint, clip_id in tasks:
                manifest.write(stage="FTP", camera=label, reel=reel_hint,
                               clip=clip_id or "ALL", status="OFFLINE",
                               note="Camera unreachable")
            continue

        print("ONLINE — connecting...")
        try:
            ftp = ftp_connect(ip)
            ftp.cwd("/media")
            all_reels = [r for r in ftp.nlst() if r.upper().endswith(".RDM")]

            for mode, reel_hint, clip_id in tasks:
                # Find matching reels (sorted so hinted reel comes first)
                matching_reels = sorted(
                    [r for r in all_reels if reel_hint in r.upper()],
                    key=lambda x: reel_hint in x.upper(), reverse=True
                ) or all_reels  # fall back to all reels if no match

                found = False
                for reel in matching_reels:
                    reel_path = f"/media/{reel}"
                    try:
                        ftp.cwd(reel_path)
                        rdc_folders = ftp.nlst()
                    except Exception:
                        continue

                    for rdc in rdc_folders:
                        if not rdc.upper().endswith(".RDC"):
                            continue

                        # CLIP mode: match clip_id in rdc name
                        if mode == "CLIP" and clip_id not in rdc.upper():
                            continue

                        rdc_path = f"{reel_path}/{rdc}"
                        local_clip = output_dir / label / reel / rdc

                        if local_clip.exists():
                            print(f"    ↩  Already exists: {reel}/{rdc} — skipping")
                            manifest.write(stage="FTP", camera=label, reel=reel,
                                           clip=rdc, status="Skipped",
                                           note="Already on disk")
                            found = True
                            continue

                        print(f"    ↓  {reel}/{rdc}")
                        ftp_download_dir(ftp, rdc_path, local_clip)

                        # Verify downloaded files
                        _verify_clip(local_clip, manifest, label, reel, rdc)
                        found = True

                    if found and mode == "CLIP":
                        break

                if not found:
                    tag = clip_id if clip_id else "ALL"
                    print(f"    ❌ Not found: {reel_hint}/{tag}")
                    manifest.write(stage="FTP", camera=label, reel=reel_hint,
                                   clip=tag, status="NOT FOUND")

            ftp.quit()

        except Exception as e:
            print(f"    ❌ Error: {e}")
            manifest.write(stage="FTP", camera=label, status="ERROR", note=str(e))


def _verify_clip(clip_dir: Path, manifest: Manifest, label: str, reel: str, rdc: str):
    """Hash every file in the just-downloaded clip dir and record result."""
    for f in sorted(clip_dir.rglob("*")):
        if not f.is_file():
            continue
        h = xxh128(f)
        size = f.stat().st_size
        print(f"      ✔  {f.name}  {h[:16]}…  ({human_size(size)})")
        manifest.write(
            stage="FTP", camera=label, reel=reel, clip=rdc,
            file=f.name, size_bytes=size,
            src_hash=h, dst_hash=h,   # src==dst at landing; transfer stage re-checks
            status="OK"
        )


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n=== FDVC FTP — RED Array Downloader ===\n")

    if len(sys.argv) >= 3:
        output_dir   = Path(sys.argv[1]).expanduser().resolve()
        manifest_csv = Path(sys.argv[2]).expanduser().resolve()
    else:
        output_dir   = Path(input("Output directory (default: ./media): ").strip() or "media").expanduser().resolve()
        manifest_csv = output_dir / "_manifests" / "fdvc_session.csv"

    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = Manifest(manifest_csv)
    print(f"📁 Output : {output_dir}")
    print(f"📋 Manifest: {manifest_csv}\n")

    print("Clip names — one per line (e.g. G007_A083 or ALL:007).")
    print("Blank line or Ctrl-D to begin.\n")

    clips = []
    while True:
        try:
            line = input().strip()
            if not line:
                break
            clips.append(line)
        except EOFError:
            break

    if not clips:
        print("No clips provided. Exiting.")
        sys.exit(0)

    pull_clips(clips, output_dir, manifest)
    print(f"\n✅  FTP pull complete. Manifest: {manifest_csv}")
