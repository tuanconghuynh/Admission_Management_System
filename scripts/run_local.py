"""Local Windows/Linux development runner with a separate durable email worker."""
import argparse
import os
from pathlib import Path
import subprocess
import sys


def main():
    root = Path(__file__).resolve().parents[1]
    os.chdir(root)
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--lan-ip')
    parser.add_argument('--check', action='store_true', help='Verify migrations and application startup, then exit without starting email worker')
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        raise SystemExit('Port must be 1–65535')
    if args.lan_ip:
        import ipaddress
        address = str(ipaddress.IPv4Address(args.lan_ip))
        os.environ['ALLOWED_HOSTS'] = 'localhost,127.0.0.1,' + address
    from app.core.config import settings
    if settings.ENVIRONMENT == 'production':
        raise SystemExit('Use the production deployment instructions, not the development runner')
    from alembic.config import Config
    from alembic import command
    from sqlalchemy.exc import OperationalError
    try:
        command.upgrade(Config(str(root/'alembic.ini')), 'head')
    except OperationalError as exc:
        code = exc.orig.args[0] if getattr(exc.orig, 'args', None) else 'unknown'
        if code == 1524:
            raise SystemExit('MySQL 1524: tai khoan dang dung mysql_native_password khong duoc ho tro. Can tai khoan caching_sha2_password va cap nhat DATABASE_URL trong .env.') from None
        raise SystemExit(f'Khong ket noi duoc MySQL (ma loi {code}). Kiem tra dich vu MySQL va DATABASE_URL trong .env.') from None
    if args.check:
        from starlette.testclient import TestClient
        from app.main import app
        with TestClient(app, base_url='http://localhost') as client:
            for path in ('/api/health', '/api/ready', '/auth_login.html'):
                response = client.get(path)
                if response.status_code != 200:
                    raise SystemExit(f'Startup check failed: {path} HTTP {response.status_code}')
        print('Database migration, application startup, readiness and login page checks passed. No emails sent.')
        return
    worker = subprocess.Popen([sys.executable, '-m', 'scripts.email_worker'], cwd=root,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    try:
        import uvicorn
        print(f'Open http://{args.lan_ip or "127.0.0.1"}:{args.port}; Ctrl+C to stop')
        uvicorn.run('app.main:app', host=args.host, port=args.port, reload=True)
    finally:
        worker.terminate()
        worker.wait(timeout=10)


if __name__ == '__main__':
    main()
