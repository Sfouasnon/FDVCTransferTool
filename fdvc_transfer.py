#!/usr/bin/env python3
"""
FDVC Transfer — Move landed footage from local storage → network destination.

Preserves RED hierarchy:  CAMERA_LABEL/REEL.RDM/CLIP.RDC/files
Uses xxhash128 for post-copy verification.
Skips files already present at destination with matching hash.

Usage (interactive):  python3 fdvc_transfer.py
Usage (scripted):
  python3 fdvc_transfer.py <src_root> <dst_root> <project> <manifest_csv> [clip_filter...]

clip_filter (optional): space-separated labels like "GA GB" or clip names like "G007_A083"
  Omit to transfer everything under src_root.
"""
import sys
import shutil
import threading
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, str(Path(__file__).parent))
from fdvc_core import xxh128, Manifest, human_size, write_html_report  # noqa: F401


# ── Discovery ─────────────────────────────────────────────────────────────────
# Folders to always skip regardless of media type
_SKIP_DIRS = {"_checksums", "_manifests", "__pycache__"}

def discover_files(src_root: Path, clip_filter: list[str]) -> list[tuple[Path, str, str, str]]:
    """
    Return list of (file, camera, reel, clip) tuples covering ALL media under src_root.

    Strategy:
      - RED media:   walks CAMERA/REEL.RDM/CLIP.RDC hierarchy, tags accordingly
      - Everything else (blackmagic, hyperdeck, etc.): included as-is, camera/reel/clip
        derived from the first three path components relative to src_root

    clip_filter: if set, only include files whose relative path contains any token.
    """
    tokens = [t.upper() for t in clip_filter] if clip_filter else []
    results = []

    # Walk every file under src_root, skipping system dirs
    for f in sorted(src_root.rglob("*")):
        if not f.is_file():
            continue

        # Skip system/hidden
        if any(part in _SKIP_DIRS or part.startswith(".") for part in f.parts):
            continue

        rel   = f.relative_to(src_root)
        parts = rel.parts

        # Apply clip filter
        if tokens and not any(tok in str(rel).upper() for tok in tokens):
            continue

        # Derive metadata from path depth
        camera = parts[0] if len(parts) >= 1 else ""
        reel   = parts[1] if len(parts) >= 2 else ""
        clip   = parts[2] if len(parts) >= 3 else ""

        results.append((f, camera, reel, clip))

    return results


# ── Per-file transfer + verify ────────────────────────────────────────────────
def transfer_file(src: Path, dst: Path, manifest: Manifest,
                  camera: str, reel: str, clip: str,
                  verify: bool, lock: threading.Lock) -> bool:
    """
    Copy src → dst if dst doesn't exist or hashes differ.
    Returns True on success.
    """
    dst.parent.mkdir(parents=True, exist_ok=True)
    size      = src.stat().st_size
    size_h    = human_size(size)

    # Skip if already there and hash matches
    if dst.exists():
        if verify:
            s_hash = xxh128(src)
            d_hash = xxh128(dst)
            if s_hash == d_hash:
                with lock:
                    manifest.write(stage="Transfer", camera=camera, reel=reel, clip=clip,
                                   file=src.name, size_bytes=size, size_human=size_h,
                                   src_hash=s_hash, dst_hash=d_hash,
                                   status="Skipped", note="Already verified at dst")
                return True
        else:
            with lock:
                manifest.write(stage="Transfer", camera=camera, reel=reel, clip=clip,
                               file=src.name, size_bytes=size, size_human=size_h,
                               status="Skipped", note="Already at dst (no verify)")
            return True

    # Copy
    shutil.copy2(src, dst)

    if verify:
        s_hash = xxh128(src)
        d_hash = xxh128(dst)
        ok     = s_hash == d_hash
        status = "Verified" if ok else "FAIL"
        note   = "" if ok else "Hash mismatch after copy"
        with lock:
            manifest.write(stage="Transfer", camera=camera, reel=reel, clip=clip,
                           file=src.name, size_bytes=size, size_human=size_h,
                           src_hash=s_hash, dst_hash=d_hash,
                           status=status, note=note)
        return ok
    else:
        with lock:
            manifest.write(stage="Transfer", camera=camera, reel=reel, clip=clip,
                           file=src.name, size_bytes=size, size_human=size_h,
                           status="Copied")
        return True


# ── Main transfer engine ──────────────────────────────────────────────────────
def run_transfer(src_root: Path, dst_root: Path, project: str,
                 manifest: Manifest, clip_filter: list[str],
                 threads: int = 4, verify: bool = True):

    files_meta = discover_files(src_root, clip_filter)
    if not files_meta:
        print("❌  No files found. Check source path or clip filter.")
        return

    # Build transfer list: (src, dst, camera, reel, clip)
    files: list[tuple[Path, Path, str, str, str]] = [
        (f, dst_root / f.relative_to(src_root), cam, reel, clip)
        for f, cam, reel, clip in files_meta
    ]

    total_bytes = sum(f[0].stat().st_size for f in files)
    print(f"\nProject  : {project}")
    print(f"Files    : {len(files)}")
    print(f"Payload  : {human_size(total_bytes)}")
    print(f"Verify   : {'xxhash128' if verify else 'OFF'}")
    print(f"Threads  : {threads}")

    # Capacity check
    stat = shutil.disk_usage(dst_root)
    if total_bytes > stat.free:
        print(f"❌  Insufficient space at destination "
              f"(need {human_size(total_bytes)}, have {human_size(stat.free)})")
        return

    confirm = input("\nBegin transfer? (y/n): ").strip().lower()
    if confirm != "y":
        return

    print(f"\n{'─'*60}")
    lock = threading.Lock()
    ok_count = 0
    fail_count = 0

    with ThreadPoolExecutor(max_workers=threads) as pool:
        futures = {
            pool.submit(transfer_file, src, dst, manifest, cam, reel, clip, verify, lock): src
            for src, dst, cam, reel, clip in files
        }
        done = 0
        for future in as_completed(futures):
            done += 1
            src_path = futures[future]
            try:
                success = future.result()
                if success:
                    ok_count += 1
                    print(f"  ✔  [{done}/{len(files)}]  {src_path.name}")
                else:
                    fail_count += 1
                    print(f"  ✘  [{done}/{len(files)}]  {src_path.name}  ← HASH MISMATCH")
            except Exception as e:
                fail_count += 1
                print(f"  ✘  [{done}/{len(files)}]  {src_path.name}  ← ERROR: {e}")
                with lock:
                    manifest.write(stage="Transfer", file=src_path.name,
                                   status="ERROR", note=str(e))

    print(f"\n{'─'*60}")
    print(f"✔ OK: {ok_count}   ✘ FAIL: {fail_count}   Total: {len(files)}")
    return ok_count, fail_count


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n=== FDVC Transfer — Local → Network ===\n")

    if len(sys.argv) >= 5:
        src_root     = Path(sys.argv[1]).expanduser().resolve()
        dst_root     = Path(sys.argv[2]).expanduser().resolve()
        project      = sys.argv[3]
        manifest_csv = Path(sys.argv[4]).expanduser().resolve()
        clip_filter  = sys.argv[5:] if len(sys.argv) > 5 else []
    else:
        src_root     = Path(input("Source (local storage root): ").strip()).expanduser().resolve()
        dst_root     = Path(input("Destination (network root): ").strip()).expanduser().resolve()
        project      = input("Project name: ").strip()
        manifest_csv = src_root / "_manifests" / "fdvc_session.csv"
        clip_f       = input("Clip filter (blank = transfer all, or e.g. GA G007_A083): ").strip()
        clip_filter  = clip_f.split() if clip_f else []

    threads_in = input("Threads (default 4): ").strip()
    threads    = int(threads_in) if threads_in.isdigit() else 4
    verify_in  = input("Verify with xxhash128? (y/n, default y): ").strip().lower()
    verify     = verify_in != "n"

    dst_root.mkdir(parents=True, exist_ok=True)
    manifest = Manifest(manifest_csv)

    result = run_transfer(src_root, dst_root, project, manifest,
                          clip_filter, threads=threads, verify=verify)

    if result:
        ok, fail = result
        # Generate HTML report
        ts      = datetime.now().strftime("%Y%m%d_%H%M%S")
        report  = manifest_csv.parent / f"FDVC_Report_{project}_{ts}.html"
        write_html_report(manifest_csv, project, report)
        print(f"\n📄  Report: {report}")

    print("\n✅  Transfer complete.")
