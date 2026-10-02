"""Check JavaScript syntax using Node.js available on the machine."""
import argparse
import subprocess
from pathlib import Path
parser = argparse.ArgumentParser()
parser.add_argument('--node', default='node')
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
for path in (root/'app/templates/js').glob('*.js'):
    subprocess.run([args.node, '--check', str(path)], check=True)
print('JavaScript syntax checks passed')
for path in (root/'tests').glob('*_js.cjs'):
    subprocess.run([args.node, str(path)], check=True)
