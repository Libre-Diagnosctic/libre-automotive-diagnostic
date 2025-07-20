# utils/log_manager.py
import os, json, csv, datetime, logging, shutil, atexit, tempfile
from logging.handlers import RotatingFileHandler
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
RUNTIME_DIR = Path(tempfile.gettempdir()) / "librediag_runtime"  # OS temp
JSONL = RUNTIME_DIR / "diagnostic_log.jsonl"
DEBUG = RUNTIME_DIR / "debug.log"
_enabled = False

# -----------------------------------------------------------------------
def configure_logging(enable: bool):
    global _enabled
    _enabled = enable

    if not enable:
        logging.disable(logging.CRITICAL)
        return

    _fresh_runtime_dir()

    handler = RotatingFileHandler(DEBUG, maxBytes=1_000_000, backupCount=3)
    logging.basicConfig(
        level=logging.INFO,
        handlers=[handler],
        format="%(asctime)s %(levelname)s: %(message)s"
    )

    # register exit hook (fires even if packaged as exe/appimage)
    atexit.register(_export_and_purge)

def save_session(results: dict, dtcs: list | None):
    if not _enabled:
        return
    JSONL.write_text("", encoding="utf-8") if not JSONL.exists() else None
    payload = {
        "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
        "results": results,
        "dtcs": dtcs or []
    }
    with open(JSONL, "a", encoding="utf-8") as f:
        f.write(json.dumps(payload) + "\n")

# -----------------------------------------------------------------------
def _fresh_runtime_dir():
    if RUNTIME_DIR.exists():
        shutil.rmtree(RUNTIME_DIR, ignore_errors=True)
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

def _export_and_purge():
    """
    1) Convert the session JSONL → CSV and let user pick location
    2) Remove runtime directory entirely
    """
    if not _enabled:
        return

    logging.shutdown()  # flush debug.log

    # nothing recorded? skip
    if not JSONL.exists() or JSONL.stat().st_size == 0:
        shutil.rmtree(RUNTIME_DIR, ignore_errors=True)
        return

    # ---------- turn JSONL into CSV in temp ----------------------------
    tmp_csv = RUNTIME_DIR / "session.csv"
    with open(JSONL, encoding="utf-8") as src, open(tmp_csv, "w", newline="") as out_fp:
        writer = None
        for line in src:
            obj = json.loads(line)
            flat = {**obj["results"], "dtcs": ";".join(obj["dtcs"]), "timestamp": obj["timestamp"]}
            if writer is None:
                writer = csv.DictWriter(out_fp, fieldnames=flat.keys())
                writer.writeheader()
            writer.writerow(flat)

    # ---------- ask user where to save --------------------------------
    try:
        import tkinter.filedialog as fd
        dest = fd.asksaveasfilename(
            title="Save diagnostic CSV",
            initialfile=f"libre_diagnostic_{datetime.datetime.now():%Y%m%d_%H%M%S}.csv",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if dest:
            shutil.move(tmp_csv, dest)
    except Exception:
        # if GUI closed unexpectedly just discard
        pass

    # ---------- purge everything --------------------------------------
    shutil.rmtree(RUNTIME_DIR, ignore_errors=True)
