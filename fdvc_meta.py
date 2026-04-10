#!/usr/bin/env python3
"""
FDVC Meta — Scrape LTC timecode and FPS from R3D files via REDline.
Appends rows to the session manifest CSV.

Usage (interactive):  python3 fdvc_meta.py
Usage (scripted):     python3 fdvc_meta.py <r3d_root> <per_frame_dir> <manifest_csv>
"""
import sys
import csv
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from fdvc_core import Manifest, parse_camera_label


def find_redline() -> str:
    candidates = [
        shutil.which("REDline"),
        "/Applications/REDCINE-X PRO.app/Contents/MacOS/REDline",
        "/usr/local/bin/REDline",
        "/opt/homebrew/bin/REDline",
    ]
    for c in candidates:
        if c and Path(c).exists():
            return c
    raise RuntimeError("REDline not found. Add it to PATH or install REDCINE-X PRO.")


def run_redline(redline: str, r3d: Path, out_csv: Path):
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    cmd = [redline, "--i", str(r3d), "--printMeta", "5", "--useMeta"]
    with open(out_csv, "w", encoding="utf-8", newline="") as f:
        proc = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        if out_csv.exists() and out_csv.stat().st_size > 0:
            return  # REDline quirk — output exists despite non-zero exit
        raise RuntimeError(proc.stderr.strip() or f"REDline failed on {r3d.name}")


def normalize_tc(tc) -> str:
    return str(tc).strip().replace(".", ":") if tc else ""


def estimate_fps(df) -> str:
    import pandas as pd
    if "Timestamp" not in df.columns or len(df) < 2:
        return ""
    ts = pd.to_numeric(df["Timestamp"], errors="coerce").dropna()
    deltas = ts.diff().dropna()
    if deltas.empty or float(deltas.median()) <= 0:
        return ""
    fps = 1_000_000.0 / float(deltas.median())
    common = [23.976, 24, 25, 29.97, 30, 47.952, 48, 50, 59.94, 60,
              90, 96, 100, 119.88, 120]
    nearest = min(common, key=lambda x: abs(x - fps))
    fps = nearest if abs(nearest - fps) < 0.1 else fps
    return str(int(round(fps))) if abs(fps - round(fps)) < 0.001 else f"{fps:.3f}"


def summarize(per_frame_csv: Path, r3d: Path) -> dict:
    import pandas as pd
    df = pd.read_csv(per_frame_csv)
    if df.empty:
        raise RuntimeError(f"Empty CSV: {per_frame_csv.name}")
    df.columns = [c.strip() for c in df.columns]

    tc_col = next((c for c in ["Timecode","timecode","TC","Abs Timecode","Edge Timecode"]
                   if c in df.columns), None)
    if not tc_col:
        raise RuntimeError(f"No timecode column in {per_frame_csv.name}. Cols: {list(df.columns)}")

    ts_col = next((c for c in ["Timestamp","timestamp","Time Stamp"] if c in df.columns), None)

    fps = ""
    if ts_col:
        fps = estimate_fps(df.rename(columns={ts_col: "Timestamp"}))

    return {
        "camera": parse_camera_label(r3d.name),
        "file":   r3d.name,
        "ltc_in": normalize_tc(df[tc_col].iloc[0]),
        "ltc_out": normalize_tc(df[tc_col].iloc[-1]),
        "fps":    fps,
    }


def run_meta(r3d_root: Path, per_frame_dir: Path, manifest: Manifest,
             master_csv: Path):
    r3d_files = sorted(r3d_root.rglob("*.R3D"))
    if not r3d_files:
        print("No .R3D files found.")
        return

    try:
        redline = find_redline()
    except RuntimeError as e:
        print(f"❌  {e}")
        return

    rows = []
    for r3d in r3d_files:
        pf_csv = per_frame_dir / f"{r3d.stem}_per_frame.csv"
        print(f"  → {r3d.name}", end="  ", flush=True)
        try:
            run_redline(redline, r3d, pf_csv)
            info = summarize(pf_csv, r3d)
            rows.append(info)
            print(f"✔  {info['ltc_in']} → {info['ltc_out']}  {info['fps']}fps")
            manifest.write(
                stage="Meta", camera=info["camera"], file=info["file"],
                note=f"LTC {info['ltc_in']}→{info['ltc_out']} {info['fps']}fps",
                status="OK"
            )
        except Exception as e:
            print(f"✘  {e}")
            manifest.write(stage="Meta", file=r3d.name, status="FAIL", note=str(e))

    if not rows:
        print("No rows to write.")
        return

    master_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(master_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["camera","file","ltc_in","ltc_out","fps"])
        w.writeheader()
        w.writerows(rows)

    print(f"\n📋  Master LTC CSV ({len(rows)} clips): {master_csv}")


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n=== FDVC Meta — R3D LTC Scraper ===\n")

    if len(sys.argv) == 4:
        r3d_root     = Path(sys.argv[1]).expanduser().resolve()
        per_frame_dir = Path(sys.argv[2]).expanduser().resolve()
        manifest_csv = Path(sys.argv[3]).expanduser().resolve()
    else:
        r3d_root      = Path(input("R3D folder: ").strip()).expanduser().resolve()
        per_frame_dir = Path(input("Per-frame CSV output folder: ").strip()).expanduser().resolve()
        manifest_csv  = r3d_root / "_manifests" / "fdvc_session.csv"

    ts_tag    = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    master_csv = per_frame_dir / f"master_ltc_{ts_tag}.csv"
    manifest  = Manifest(manifest_csv)

    run_meta(r3d_root, per_frame_dir, manifest, master_csv)
    print("\n✅  Meta scrape complete.")
