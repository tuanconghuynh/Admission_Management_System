import os
import sys
from pathlib import Path
root = Path(__file__).resolve().parents[1]
os.chdir(root)
sys.path.insert(0, str(root))
import pytest
raise SystemExit(pytest.main(["tests", "-q", "--tb=short", *sys.argv[1:]]))
