import logging
import time
import argparse
from app.services.email_queue import process_one
from app.core.config import settings
from app.db.session import engine
from sqlalchemy import text


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    if settings.ENVIRONMENT == "production":
        with engine.connect() as connection:
            if connection.execute(text("SELECT version_num FROM alembic_version")).scalar() != "20261003_02":
                raise RuntimeError("Run alembic upgrade head before starting the worker")
    while True:
        try:
            worked = process_one()
        except Exception:
            logging.exception("Email worker failed")
            if args.once:
                raise
            worked = False
        if args.once:
            return
        if not worked:
            time.sleep(2)


if __name__ == "__main__":
    main()
