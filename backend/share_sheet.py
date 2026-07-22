"""Share the spreadsheet with the service account, then set up sync."""
import json, os, subprocess, sys, time
from pathlib import Path

# ── Config ──────────────────────────────────────────────────────────────
SHEET_ID = "1010Qr316QWW7TpCBx9hCR5Eu5nQQDhgSrU-Ddwg9WtE"
SA_EMAIL = "farm-erp-service@farm-erp-ea3b8.iam.gserviceaccount.com"
CRED_FILE = Path(__file__).parent / "credentials" / "farm-erp-ea3b8-e64401ef799d.json"
RAILWAY = r"C:\Users\amdof\AppData\Roaming\npm\railway.cmd"

# ── Step 1: Share sheet with service account ───────────────────────────
print("=" * 60)
print("STEP 1: Share spreadsheet with service account")
print("=" * 60)

# Use OAuth to authenticate as user and share the sheet
# We'll use the google-auth-oauthlib flow (already installed)
oa_script = '''
import json, os, pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
SHEET_ID = "1010Qr316QWW7TpCBx9hCR5Eu5nQQDhgSrU-Ddwg9WtE"
SA_EMAIL = "farm-erp-service@farm-erp-ea3b8.iam.gserviceaccount.com"
TOKEN_FILE = os.path.join(os.environ.get("USERPROFILE", "."), ".farmerp_drive_token.pickle")

creds = None

# Load saved token
if os.path.exists(TOKEN_FILE):
    with open(TOKEN_FILE, "rb") as t:
        creds = pickle.load(t)

# Refresh or get new token
if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        flow = InstalledAppFlow.from_client_config(
            {
                "installed": {
                    "client_id": "764086051850-6qr4p6gpi6hn506pt8ejeqoasv2e6iqr.apps.googleusercontent.com",
                    "client_secret": "d-FL95Q19q7MQmFpd7hHD0Ty",
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": ["http://localhost"]
                }
            },
            SCOPES
        )
        creds = flow.run_local_server(port=0, prompt="consent")
    
    with open(TOKEN_FILE, "wb") as t:
        pickle.dump(creds, t)

# Share the sheet
drive = build("drive", "v3", credentials=creds)
permission = {
    "type": "user",
    "role": "writer",
    "emailAddress": SA_EMAIL
}
result = drive.permissions().create(
    fileId=SHEET_ID,
    body=permission,
    sendNotificationEmail=False
).execute()

print("SHARED: " + result.get("id", "unknown"))
print("Service account " + SA_EMAIL + " now has Editor access to the sheet!")
'''

# Run the OAuth sharing
result = subprocess.run(
    ["python", "-c", oa_script],
    capture_output=True, text=True, timeout=300
)

if result.returncode == 0 and "SHARED:" in result.stdout:
    print("  [OK] Spreadsheet shared with service account!")
    print("  " + result.stdout.strip())
elif result.returncode == 0:
    print("  [OK] " + result.stdout.strip())
else:
    print("  [WARN] OAuth failed: " + (result.stderr or result.stdout)[:300])
    print("  You need to manually share the spreadsheet:")
    print("  1. Open: https://docs.google.com/spreadsheets/d/" + SHEET_ID + "/edit")
    print("  2. Click Share > Add: " + SA_EMAIL)
    print("  3. Role: Editor > Click Share")
    input("  Press Enter after you've shared the sheet... ")

# ── Step 2: Deploy to Railway ──────────────────────────────────────────
print("\\n" + "=" * 60)
print("STEP 2: Deploying to Railway...")
print("=" * 60)

result = subprocess.run(
    [RAILWAY, "up", "--service", "farmerp-backend", "--detach"],
    capture_output=True, text=True, timeout=300
)
if result.returncode == 0:
    print("  [OK] Deployment started!")
else:
    print("  [WARN] " + (result.stderr or result.stdout)[:200])
    print("  Please deploy manually: cd backend && railway up --detach")

# ── Step 3: Wait for deploy and run backfill ───────────────────────────
print("\\n" + "=" * 60)
print("STEP 3: Waiting for deployment (60s)...")
print("=" * 60)
time.sleep(60)

print("\\nRunning sheets_backfill...")
result = subprocess.run(
    [RAILWAY, "run", "python", "manage.py", "sheets_backfill"],
    capture_output=True, text=True, timeout=300
)
if result.returncode == 0:
    print("  [OK] Backfill completed!")
    print("  " + result.stdout[-500:])
else:
    err = (result.stderr or result.stdout)[:500]
    print("  [WARN] Backfill issue: " + err)
    print("  Try manually: railway run python manage.py sheets_backfill")

print("\\n" + "=" * 60)
print("SETUP COMPLETE!")
print("=" * 60)
print("Open your sheet: https://docs.google.com/spreadsheets/d/" + SHEET_ID + "/edit")
