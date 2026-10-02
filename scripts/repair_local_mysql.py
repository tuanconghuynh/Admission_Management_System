"""Repair obsolete local MySQL authentication without altering existing accounts."""
import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import tarfile
import uuid

import pymysql
from sqlalchemy.engine import make_url, URL


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mysqldump', required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    os.chdir(root)
    from app.core.config import settings
    url = make_url(settings.SQLALCHEMY_DATABASE_URI)
    if settings.ENVIRONMENT == 'production' or url.host not in ('localhost', '127.0.0.1') or url.get_backend_name() != 'mysql' or not url.database:
        raise SystemExit('This repair only supports a local development MySQL database.')
    if not args.apply:
        print('Will back up the configured local database, create a dedicated caching_sha2_password user and update .env. Add --apply to proceed.')
        return
    admin = pymysql.connect(host='127.0.0.1', port=url.port or 3306, user='root', password='', charset='utf8mb4')
    with admin.cursor() as cursor:
        cursor.execute('SELECT SCHEMA_NAME FROM information_schema.SCHEMATA WHERE SCHEMA_NAME=%s', (url.database,))
        if not cursor.fetchone():
            raise SystemExit('Configured database does not exist; no changes made.')
    backup = root / 'backups' / ('auth-repair-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ'))
    backup.mkdir(parents=True)
    with (backup / 'database.sql').open('wb') as target:
        result = subprocess.run([args.mysqldump, '--host=127.0.0.1', '--port=' + str(url.port or 3306),
            '--user=root', '--single-transaction', '--quick', '--no-tablespaces', '--hex-blob',
            '--default-character-set=utf8mb4', url.database], stdout=target, stderr=subprocess.PIPE,
            env={**os.environ, 'MYSQL_PWD': ''})
    if result.returncode:
        raise SystemExit('Backup failed; no account or configuration changes made.')
    shutil.copy2(root / '.env', backup / 'env.before')
    with tarfile.open(backup / 'receipts.tar.gz', 'w:gz') as archive:
        for name, directory in (('configured_receipts', settings.receipts_path), ('legacy_receipts', root / 'assets' / 'receipts')):
            if directory.exists():
                archive.add(directory, arcname=name)
    username = 'ams_local_' + uuid.uuid4().hex[:10]
    password = secrets.token_urlsafe(36)
    database_identifier = '`' + url.database.replace('`', '``') + '`'
    with admin.cursor() as cursor:
        cursor.execute("CREATE USER %s@'localhost' IDENTIFIED WITH caching_sha2_password BY %s", (username, password))
        cursor.execute("GRANT ALL PRIVILEGES ON " + database_identifier + ".* TO %s@'localhost'", (username,))
    admin.close()
    connection = pymysql.connect(host='127.0.0.1', port=url.port or 3306, user=username, password=password, database=url.database)
    connection.close()
    new_url = URL.create('mysql+pymysql', username=username, password=password, host='127.0.0.1',
        port=url.port or 3306, database=url.database, query={'charset': 'utf8mb4'}).render_as_string(hide_password=False)
    env_path = root / '.env'
    content = env_path.read_text(encoding='utf-8')
    if re.search(r'^DATABASE_URL=', content, flags=re.M):
        content = re.sub(r'^DATABASE_URL=[^\r\n]*', lambda match: 'DATABASE_URL=' + new_url, content, flags=re.M)
    else:
        content += '\nDATABASE_URL=' + new_url + '\n'
    env_path.write_text(content, encoding='utf-8')
    print('Local MySQL account repaired; database and existing accounts preserved.')
    print('Backup:', backup)


if __name__ == '__main__':
    try:
        main()
    except pymysql.MySQLError as exc:
        raise SystemExit('MySQL repair failed (code ' + str(exc.args[0]) + '). No credentials printed.') from None
