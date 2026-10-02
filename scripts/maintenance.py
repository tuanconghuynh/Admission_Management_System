"""Clean expired rate windows and orphan UUID draft PDFs; dry run by default."""
import argparse
import re
import time
from pathlib import Path
from datetime import datetime, timedelta
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.operations import RateWindow, EmailJob


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--days", type=int, default=30)
    args = parser.parse_args()
    if args.days < 7:
        raise SystemExit("Retention must be at least 7 days")
    with SessionLocal.begin() as db:
        cutoff = int(time.time()) // 60 - 1440
        query = db.query(RateWindow).filter(RateWindow.window < cutoff)
        count = query.count()
        if args.apply:
            query.delete(synchronize_session=False)
        # Preserve attachments referenced by any job, including failed/uncertain.
        referenced = {Path(name).resolve() for (attachments,) in db.query(EmailJob.attachments).yield_per(500) for name in (attachments or [])}
    cutoff_time = time.time() - args.days * 86400
    paths = [path for path in settings.receipts_path.glob("*.pdf")
        if re.fullmatch(r"[a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12}\.pdf", path.name)
        and path.resolve() not in referenced and path.stat().st_mtime < cutoff_time]
    if args.apply:
        for path in paths:
            path.unlink()
    print(f"{'Removed' if args.apply else 'Would remove'} {count} expired rate windows and {len(paths)} orphan draft PDFs")


if __name__ == "__main__":
    main()
