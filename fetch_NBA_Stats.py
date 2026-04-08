import subprocess, sys, os

result_nba = subprocess.run(
    [sys.executable, "-m", "pip", "install", "nba_api", f"--target=/tmp/site-packages", "-q"],
    capture_output=True, text=True
)
print("nba_api return code:", result_nba.returncode)
if result_nba.returncode != 0:
    print("nba_api stderr:", result_nba.stderr[:400])
else:
    print("nba_api installed to /tmp/site-packages")

result_bball = subprocess.run(
    [sys.executable, "-m", "pip", "install", "basketball_reference_web_scraper",
     f"--target=/tmp/site-packages", "-q"],
    capture_output=True, text=True
)
print("bball_ref return code:", result_bball.returncode)
if result_bball.returncode != 0:
    print("bball_ref stderr:", result_bball.stderr[:400])
else:
    print("bball_ref installed to /tmp/site-packages")

# Add /tmp/site-packages to path
if "/tmp/site-packages" not in sys.path:
    sys.path.insert(0, "/tmp/site-packages")

# Verify imports
for pkg, import_name in [("nba_api", "nba_api"), ("bball_ref", "basketball_reference_web_scraper")]:
    try:
        __import__(import_name.replace("-", "_"))
        print(f"{pkg}: import OK")
    except ImportError as e:
        print(f"{pkg}: import FAILED - {e}")
