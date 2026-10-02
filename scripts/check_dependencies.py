from pathlib import Path
from importlib.metadata import version, PackageNotFoundError

requirements = Path(__file__).resolve().parents[1] / 'requirements.lock'
for line in requirements.read_text(encoding='utf-8').splitlines():
    if not line or line.startswith('#'):
        continue
    name, expected = line.split('==', 1)
    try:
        if version(name) != expected:
            raise SystemExit(1)
    except PackageNotFoundError:
        raise SystemExit(1)
print('Dependencies match requirements.lock')
