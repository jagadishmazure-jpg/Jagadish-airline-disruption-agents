"""Print the real test total (never swallows it with -qq)."""
import subprocess
import sys

out = subprocess.run(
    [sys.executable, "-m", "pytest", "tests/", "-q"],
    capture_output=True, text=True, cwd=__file__.rsplit("/", 2)[0],
)
print(out.stdout.strip().splitlines()[-1])
print(out.stderr.strip().splitlines()[-1:] if out.returncode else "")
sys.exit(out.returncode)
