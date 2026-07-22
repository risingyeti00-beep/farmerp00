"""Set Railway environment variables for Google Sheets sync."""
import json
import subprocess
import sys
from pathlib import Path

RAILWAY_CLI = r"C:\Users\amdof\AppData\Roaming\npm\railway.cmd"
CRED_FILE = Path(__file__).parent / "credentials" / "farm-erp-ea3b8-e64401ef799d.json"
TARGET_SHEET_ID = "1010Qr316QWW7TpCBx9hCR5Eu5nQQDhgSrU-Ddwg9WtE"

def set_railway_var(key, value):
    """Set a Railway env var using subprocess."""
    result = subprocess.run(
        [RAILWAY_CLI, "variables", "set", key + "=" + value],
        capture_output=True, text=True, timeout=30
    )
    if result.returncode == 0:
        print("  [OK] " + key)
        return True
    else:
        msg = (result.stderr or result.stdout or "").strip()[:200]
        print("  [FAIL] " + key + ": " + msg)
        return False

# Step 1: Set GOOGLE_SPREADSHEET_ID
print("1. Setting GOOGLE_SPREADSHEET_ID...")
set_railway_var("GOOGLE_SPREADSHEET_ID", TARGET_SHEET_ID)

# Step 2: Set GOOGLE_SERVICE_ACCOUNT_JSON
print("2. Setting GOOGLE_SERVICE_ACCOUNT_JSON...")
if CRED_FILE.exists():
    with open(CRED_FILE) as f:
        creds = json.load(f)
    minified = json.dumps(creds, separators=(",", ":"))
    ok = set_railway_var("GOOGLE_SERVICE_ACCOUNT_JSON", minified)
    if ok:
        print("   Done (" + str(len(minified)) + " chars)")
    else:
        print("   Trying alternate method...")
        # If regular method fails, write to temp file and use railway from bash
        import tempfile, os
        tmp = os.path.join(tempfile.gettempdir(), "sa_minified.json")
        with open(tmp, "w") as f:
            f.write(minified)
        print("   Saved to " + tmp + " for manual setting")
else:
    print("   ERROR: Credentials file not found at " + str(CRED_FILE))
    sys.exit(1)

# Step 3: Set GOOGLE_SHEETS_SYNC_ENABLED
print("3. Setting GOOGLE_SHEETS_SYNC_ENABLED...")
set_railway_var("GOOGLE_SHEETS_SYNC_ENABLED", "True")

print("\nDone! Verify with: railway variables | findstr GOOGLE")
