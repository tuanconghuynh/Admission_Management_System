"""Pin the production dependency closure from the environment that was tested."""
from pathlib import Path
import importlib.metadata as metadata
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

root = Path(__file__).resolve().parents[1]
direct = ['fastapi', 'uvicorn', 'pydantic', 'pydantic-settings', 'SQLAlchemy', 'PyMySQL', 'passlib', 'bcrypt',
    'itsdangerous', 'python-multipart', 'jinja2', 'reportlab', 'openpyxl', 'pandas', 'aiosmtplib', 'email-validator', 'pypdf', 'alembic', 'cryptography']
(root/'requirements.txt').write_text('\n'.join(f'{name}=={metadata.version(name)}' for name in direct) + '\n', encoding='utf-8')
pending = [(name, set()) for name in direct] + [('uvicorn', {'standard'})]
visited, locked = set(), {}
while pending:
    name, extras = pending.pop()
    normalized = canonicalize_name(name)
    fingerprint = (normalized, tuple(sorted(extras)))
    if fingerprint in visited:
        continue
    visited.add(fingerprint)
    distribution = metadata.distribution(name)
    locked[normalized] = distribution.version
    for raw in distribution.requires or []:
        req = Requirement(raw)
        if req.marker and not any(req.marker.evaluate({'extra': extra}) for extra in extras | {''}):
            continue
        pending.append((req.name, set(req.extras)))
(root/'requirements.lock').write_text('# Pinned production dependency closure (Python 3.12).\n' + '\n'.join(f'{name}=={version}' for name,version in sorted(locked.items())) + '\n', encoding='utf-8')
(root/'requirements-dev.txt').write_text('-r requirements.lock\nhttpx==' + metadata.version('httpx') + '\npytest==' + metadata.version('pytest') + '\n', encoding='utf-8')
print(f'Pinned {len(locked)} production dependencies')
