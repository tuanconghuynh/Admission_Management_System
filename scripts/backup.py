"""Backup SQL and private receipts; requires a matching mysqldump on PATH."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tarfile
from datetime import datetime, timezone
from sqlalchemy.engine import make_url
from app.core.config import settings


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="backups")
    parser.add_argument("--mysqldump", default="mysqldump")
    args = parser.parse_args()
    url = make_url(settings.SQLALCHEMY_DATABASE_URI)
    if url.get_backend_name() != "mysql" or not url.database:
        raise SystemExit("Backup requires a MySQL database")
    target = Path(args.output).resolve() / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    target.mkdir(parents=True, exist_ok=False)
    sql = target / "database.sql"
    command = [args.mysqldump, "--single-transaction", "--quick", "--no-tablespaces", "--hex-blob",
        "--default-character-set=utf8mb4", "--host=" + (url.host or "localhost"), "--port=" + str(url.port or 3306),
        "--user=" + (url.username or ""), url.database]
    environment = {**os.environ, "MYSQL_PWD": url.password or ""}
    with sql.open("wb") as output:
        result = subprocess.run(command, env=environment, stdout=output, stderr=subprocess.PIPE)
    if result.returncode:
        sql.unlink(missing_ok=True)
        raise SystemExit("mysqldump failed; no complete backup created. Check client version and database permissions.")
    archive = target / "receipts.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        if settings.receipts_path.exists():
            tar.add(settings.receipts_path, arcname="receipts")
    manifest = {}
    for path in (sql, archive):
        with path.open("rb") as source:
            manifest[path.name] = hashlib.file_digest(source, "sha256").hexdigest()
    (target/"manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("Backup created:", target)


if __name__ == "__main__":
    main()
