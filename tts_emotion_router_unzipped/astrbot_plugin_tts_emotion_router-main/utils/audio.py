from pathlib import Path
import time


def ensure_dir(p: Path):
    try:
        p.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass


def cleanup_dir(root: Path, ttl_seconds: int = 3600):
    try:
        now = time.time()
        for f in root.glob("**/*"):
            try:
                if f.is_file() and (now - f.stat().st_mtime) > ttl_seconds:
                    f.unlink()
            except Exception:
                pass
    except Exception:
        pass
