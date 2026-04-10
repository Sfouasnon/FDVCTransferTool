#!/usr/bin/env python3
"""
FDVC Core - Shared utilities for camera map, clip parsing, hashing, manifests.
"""
import os
import csv
import socket
import hashlib
import subprocess
from pathlib import Path
from datetime import datetime
from ftplib import FTP_TLS, error_perm

# ── Camera Map ────────────────────────────────────────────────────────────────
CAMERAS = {
    "AA": "172.20.114.141", "AB": "172.20.114.142", "AC": "172.20.114.143", "AD": "172.20.114.144",
    "BA": "172.20.114.145", "BB": "172.20.114.146", "BC": "172.20.114.147", "BD": "172.20.114.148",
    "CA": "172.20.114.149", "CB": "172.20.114.150", "CC": "172.20.114.151", "CD": "172.20.114.152",
    "DA": "172.20.114.153", "DB": "172.20.114.154", "DC": "172.20.114.155", "DD": "172.20.114.156",
    "EA": "172.20.114.157", "EB": "172.20.114.158", "EC": "172.20.114.159", "ED": "172.20.114.160",
    "FA": "172.20.114.161", "FB": "172.20.114.162", "FC": "172.20.114.163", "FD": "172.20.114.164",
    "GA": "172.20.114.165", "GB": "172.20.114.166", "GC": "172.20.114.167", "GD": "172.20.114.168",
    "HA": "172.20.114.169", "HB": "172.20.114.170", "HC": "172.20.114.171", "HD": "172.20.114.172",
    "IA": "172.20.114.173", "IB": "172.20.114.174", "IC": "172.20.114.175", "ID": "172.20.114.176",
    "JA": "172.20.114.177", "JB": "172.20.114.178", "JC": "172.20.114.179", "JD": "172.20.114.180",
    "KA": "172.20.114.181", "KB": "172.20.114.182",
}

# Load credentials from env or fall back to defaults (change these or set env vars)
FTP_USER = os.environ.get("FDVC_FTP_USER", "ftp1")
FTP_PASS = os.environ.get("FDVC_FTP_PASS", "12345678")


# ── Clip Name Parsing ─────────────────────────────────────────────────────────
def parse_camera_label(filename: str) -> str:
    """
    G007_A083_... → GA
    H007_B081_... → HB
    """
    parts = Path(filename).stem.split("_")
    if len(parts) >= 2 and parts[0] and parts[1]:
        return f"{parts[0][0].upper()}{parts[1][0].upper()}"
    return ""


def parse_clip_numbers(text: str) -> set:
    """'63,64' or '60-64' → {'060','061','062','063','064'}"""
    clips = set()
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start, end = part.split("-", 1)
            for i in range(int(start), int(end) + 1):
                clips.add(f"{i:03d}")
        else:
            clips.add(f"{int(part):03d}")
    return clips


# ── Network ───────────────────────────────────────────────────────────────────
def is_online(ip: str, port: int = 21, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except OSError:
        return False


def ftp_connect(ip: str) -> FTP_TLS:
    ftp = FTP_TLS(ip, timeout=10)
    ftp.login(FTP_USER, FTP_PASS)
    ftp.prot_p()
    ftp.set_pasv(True)
    return ftp


def ftp_is_dir(ftp: FTP_TLS, path: str) -> bool:
    try:
        ftp.cwd(path)
        ftp.cwd("..")
        return True
    except Exception:
        return False


def ftp_download_dir(ftp: FTP_TLS, remote_dir: str, local_dir: Path):
    """Recursively download remote_dir → local_dir, preserving hierarchy."""
    local_dir.mkdir(parents=True, exist_ok=True)
    try:
        items = ftp.nlst(remote_dir)
    except error_perm:
        return
    for item in items:
        name = os.path.basename(item)
        if name in (".", ".."):
            continue
        local_path = local_dir / name
        if ftp_is_dir(ftp, item):
            ftp_download_dir(ftp, item, local_path)
        else:
            _ftp_download_file(ftp, item, local_path)


def _ftp_download_file(ftp: FTP_TLS, remote: str, local: Path):
    local.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    try:
        total = ftp.size(remote) or 0
    except Exception:
        pass
    transferred = [0]
    fname = local.name

    with open(local, "wb") as f:
        def cb(data):
            f.write(data)
            transferred[0] += len(data)
            _print_progress(fname, transferred[0], total)
        ftp.retrbinary(f"RETR {remote}", cb)
    print()


def _print_progress(name: str, done: int, total: int):
    pct = done / total if total else 0
    bar = "#" * int(30 * pct) + "-" * (30 - int(30 * pct))
    print(f"\r  [{bar}] {pct*100:5.1f}%  {name}", end="", flush=True)


# ── Hashing ───────────────────────────────────────────────────────────────────
def xxh128(path: Path) -> str:
    """
    Use system xxhsum if available, else fall back to hashlib xxh128 via
    pure-python xxhash (pip install xxhash).
    """
    # Try system binary first (fastest)
    for candidate in ("xxhsum", "/opt/homebrew/bin/xxhsum", "/usr/local/bin/xxhsum"):
        try:
            result = subprocess.run(
                [candidate, "-H128", "--", str(path)],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                return result.stdout.split()[0]
        except FileNotFoundError:
            continue

    # Pure-python fallback
    try:
        import xxhash
        h = xxhash.xxh128()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()
    except ImportError:
        pass

    # Last resort: sha256 (always available)
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return f"sha256:{h.hexdigest()}"


# ── Manifest ──────────────────────────────────────────────────────────────────
MANIFEST_FIELDS = ["timestamp", "stage", "camera", "reel", "clip", "file",
                   "size_bytes", "size_human", "src_hash", "dst_hash", "status", "note"]


class Manifest:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            with open(path, "w", newline="") as f:
                csv.DictWriter(f, fieldnames=MANIFEST_FIELDS).writeheader()

    def write(self, **kwargs):
        row = {k: "" for k in MANIFEST_FIELDS}
        row["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        row.update(kwargs)
        with open(self.path, "a", newline="") as f:
            csv.DictWriter(f, fieldnames=MANIFEST_FIELDS).writerow(row)


# ── HTML Report ───────────────────────────────────────────────────────────────
def write_html_report(manifest_csv: Path, project: str, out_html: Path):
    rows = []
    with open(manifest_csv, newline="") as f:
        rows = list(csv.DictReader(f))

    ok = sum(1 for r in rows if r["status"] in ("OK", "Verified", "Copied"))
    fail = sum(1 for r in rows if r["status"] in ("FAIL", "MISSING"))
    total_bytes = sum(int(r["size_bytes"]) for r in rows if r["size_bytes"].isdigit())
    total_human = human_size(total_bytes)

    logo_tag = ""
    logo_candidates = [
        Path(__file__).parent / "ILM_FDVC_LOGO.png",
        Path(__file__).parent / "ILM_FDVC_LOGO.PNG",
        Path.home() / "bin" / "ILM_FDVC_LOGO.PNG",
    ]
    for logo in logo_candidates:
        if logo.exists():
            import base64
            b64 = base64.b64encode(logo.read_bytes()).decode()
            logo_tag = f'<img src="data:image/png;base64,{b64}" class="logo">'
            break

    def row_html(r):
        cls = "ok" if r["status"] in ("OK", "Verified", "Copied") else "fail"
        size_h = human_size(int(r["size_bytes"])) if r["size_bytes"].isdigit() else r["size_bytes"]
        return (
            f'<tr class="{cls}">'
            f'<td>{r["status"]}</td><td>{r["stage"]}</td>'
            f'<td>{r["camera"]}</td><td>{r["reel"]}</td>'
            f'<td>{r["clip"]}</td><td>{r["file"]}</td>'
            f'<td style="white-space:nowrap">{size_h}</td>'
            f'<td class="hash">{r["src_hash"]}</td>'
            f'<td class="hash">{r["dst_hash"]}</td>'
            f'<td>{r["note"]}</td>'
            f'</tr>'
        )

    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>FDVC Report – {project}</title>
<style>
  body{{font-family:Helvetica,sans-serif;margin:40px;color:#222;font-size:13px}}
  .header{{border-bottom:4px solid #000;padding-bottom:16px;margin-bottom:24px;display:flex;align-items:center;gap:20px}}
  .logo{{height:80px}}
  h1{{font-size:28px;margin:0}} h2{{font-size:16px;color:#666;margin:4px 0 0}}
  .summary{{background:#f5f5f5;border:1px solid #ddd;border-radius:6px;padding:16px;margin-bottom:24px;line-height:1.8}}
  table{{width:100%;border-collapse:collapse;table-layout:fixed}}
  th{{background:#222;color:#fff;padding:10px;text-align:left;font-size:12px}}
  td{{border-bottom:1px solid #e0e0e0;padding:9px;font-size:11px;word-break:break-all}}
  tr.ok td:first-child{{color:#28a745;font-weight:bold}}
  tr.fail td:first-child{{color:#dc3545;font-weight:bold}}
  .hash{{font-family:monospace;font-size:10px;color:#555}}
</style></head><body>
<div class="header">{logo_tag}<div><h1>ILM FDVC Transfer Report</h1><h2>Project: {project}</h2></div></div>
<div class="summary">
  <strong>Generated:</strong> {datetime.now().strftime("%Y-%m-%d %H:%M")}<br>
  <strong>Total Files:</strong> {len(rows)} &nbsp;|&nbsp;
  <strong>Total Data:</strong> {total_human} &nbsp;|&nbsp;
  <strong style="color:#28a745">OK: {ok}</strong> &nbsp;|&nbsp;
  <strong style="color:#dc3545">FAIL: {fail}</strong>
</div>
<table>
<thead><tr>
  <th style="width:7%">Status</th><th style="width:7%">Stage</th>
  <th style="width:5%">Cam</th><th style="width:8%">Reel</th>
  <th style="width:10%">Clip</th><th style="width:13%">File</th>
  <th style="width:7%">Size</th>
  <th style="width:18%">Src Hash</th><th style="width:18%">Dst Hash</th>
  <th style="width:7%">Note</th>
</tr></thead><tbody>
{''.join(row_html(r) for r in rows)}
</tbody>
<tfoot>
  <tr style="background:#f0f0f0; font-weight:bold; font-size:12px;">
    <td colspan="6" style="padding:10px; text-align:right; color:#333;">TOTAL TRANSFERRED</td>
    <td style="padding:10px; white-space:nowrap; color:#222;">{total_human}</td>
    <td colspan="3" style="padding:10px; color:#333;">{ok} verified &nbsp;·&nbsp; {fail} failed &nbsp;·&nbsp; {len(rows)} files</td>
  </tr>
</tfoot></table>
</body></html>"""

    out_html.write_text(html, encoding="utf-8")
    return ok, fail


# ── Completion sound ─────────────────────────────────────────────────────────
def play_completion_sound():
    """Play swing3 sound if present, fall back to system sound."""
    candidates = [
        Path(__file__).parent / "swing3-94210.mp3",
        Path.home() / "bin" / "swing3-94210.mp3",
    ]
    for s in candidates:
        if s.exists():
            subprocess.Popen(["afplay", str(s)])
            return
    subprocess.Popen(["afplay", "/System/Library/Sounds/Blow.aiff"])


# ── Human-readable size ───────────────────────────────────────────────────────
def human_size(b: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if b < 1024:
            return f"{b:.2f} {unit}"
        b /= 1024
    return f"{b:.2f} PB"
