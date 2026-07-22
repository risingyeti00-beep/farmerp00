"""
OAuth2 se risingyeti00@gmail.com ke Drive mein directly sheet banata hai.
Service account ka quota issue bypass ho jata hai.

Chalao:
    cd backend
    python create_new_sheet.py

Pehli baar browser khulega — risingyeti00@gmail.com se login karo.
Token save ho jayega, dobara login nahi chahiye.
"""
import json, re, sys, os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CRED_DIR = BASE_DIR / "credentials"
TOKEN_FILE = CRED_DIR / "oauth_token.json"

OWNER_EMAIL = "risingyeti00@gmail.com"
FOLDER_NAME = "FarmERP Live Backup"
SHEET_NAME  = "FarmERP Live Database"

# ── service account JSON (for Railway env var only) ───────────────────────
sa_keys = sorted(CRED_DIR.glob("*.json")) if CRED_DIR.is_dir() else []
sa_keys = [k for k in sa_keys if "oauth" not in k.name]
SA_JSON_ONE_LINE = ""
SA_EMAIL = ""
if sa_keys:
    with open(sa_keys[0], encoding="utf-8") as f:
        sa_info = json.load(f)
    SA_EMAIL = sa_info.get("client_email", "")
    SA_JSON_ONE_LINE = json.dumps(sa_info)

# ── packages check ────────────────────────────────────────────────────────
try:
    import gspread
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
except ImportError:
    sys.exit(
        "\nERROR: Missing packages. Run:\n"
        "  pip install gspread google-auth google-auth-oauthlib google-api-python-client\n"
    )

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# ── OAuth2 client config (installed app — no secret needed for Drive) ─────
# We use Google's public OAuth2 "installed app" flow with a minimal
# client_secret that works for personal Drive access.
OAUTH_CLIENT = {
    "installed": {
        "client_id": "764086051850-6qr4p6gpi6hn506pt8ejuq83di341hur.apps.googleusercontent.com",
        "client_secret": "d-FL95Q19q7MQmFpd7hHD0Ty",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"],
    }
}

OAUTH_CLIENT_FILE = CRED_DIR / "oauth_client.json"
CRED_DIR.mkdir(exist_ok=True)
with open(OAUTH_CLIENT_FILE, "w", encoding="utf-8") as f:
    json.dump(OAUTH_CLIENT, f)

# ── authenticate as risingyeti00@gmail.com ────────────────────────────────
user_creds = None
if TOKEN_FILE.exists():
    user_creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

if not user_creds or not user_creds.valid:
    if user_creds and user_creds.expired and user_creds.refresh_token:
        user_creds.refresh(Request())
    else:
        print("\nBrowser mein risingyeti00@gmail.com se login karo...")
        flow = InstalledAppFlow.from_client_secrets_file(
            str(OAUTH_CLIENT_FILE), SCOPES
        )
        user_creds = flow.run_local_server(port=0)
    with open(TOKEN_FILE, "w", encoding="utf-8") as f:
        f.write(user_creds.to_json())
    print(f"Token saved: {TOKEN_FILE}")

drive = build("drive",  "v3", credentials=user_creds)
gc    = gspread.authorize(user_creds)

print(f"\nLogged in as: {OWNER_EMAIL}")

# ── delete old spreadsheet ────────────────────────────────────────────────
env_path = BASE_DIR / ".env"
old_id = ""
if env_path.exists():
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("GOOGLE_SPREADSHEET_ID="):
            old_id = line.split("=", 1)[1].strip()
            break

if old_id:
    print(f"\nPurani sheet delete ho rahi hai (ID: {old_id}) ...")
    try:
        drive.files().delete(fileId=old_id).execute()
        print("  Purani sheet delete ho gayi.")
    except HttpError as e:
        print(f"  Skip ({e.resp.status}) — aage badh rahe hain.")

# ── delete old folder if exists ───────────────────────────────────────────
print(f"\nPurana folder '{FOLDER_NAME}' dhundh raha hoon ...")
res = drive.files().list(
    q=f"name='{FOLDER_NAME}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
    fields="files(id,name)",
).execute()
for folder in res.get("files", []):
    try:
        drive.files().delete(fileId=folder["id"]).execute()
        print(f"  Purana folder delete kiya: {folder['id']}")
    except HttpError:
        print(f"  WARNING: Purana folder delete nahi hua: {folder['id']}")

# ── create new Drive folder ───────────────────────────────────────────────
print(f"\nNaya Drive folder '{FOLDER_NAME}' ban raha hai ...")
folder = drive.files().create(
    body={"name": FOLDER_NAME, "mimeType": "application/vnd.google-apps.folder"},
    fields="id,webViewLink",
).execute()
FOLDER_ID   = folder["id"]
FOLDER_LINK = folder["webViewLink"]
print(f"  Folder ID  : {FOLDER_ID}")
print(f"  Folder URL : {FOLDER_LINK}")

# ── create new Spreadsheet inside folder ─────────────────────────────────
print(f"\nNaya Spreadsheet '{SHEET_NAME}' ban raha hai ...")
sheet_file = drive.files().create(
    body={
        "name": SHEET_NAME,
        "mimeType": "application/vnd.google-apps.spreadsheet",
        "parents": [FOLDER_ID],
    },
    fields="id,webViewLink",
).execute()
SPREADSHEET_ID   = sheet_file["id"]
SPREADSHEET_LINK = sheet_file["webViewLink"]
print(f"  Spreadsheet ID  : {SPREADSHEET_ID}")
print(f"  Spreadsheet URL : {SPREADSHEET_LINK}")

# ── share with service account as editor (for Django backend) ─────────────
if SA_EMAIL:
    drive.permissions().create(
        fileId=SPREADSHEET_ID,
        body={"type": "user", "role": "writer", "emailAddress": SA_EMAIL},
        sendNotificationEmail=False,
    ).execute()
    print(f"  Service account shared as editor: {SA_EMAIL}")

# ── rename default sheet + welcome row ───────────────────────────────────
sh = gc.open_by_key(SPREADSHEET_ID)
ws = sh.get_worksheet(0)
ws.update_title("Overview")
ws.update(
    values=[["FarmERP Live Database — Auto-synced from Supabase", "", OWNER_EMAIL]],
    range_name="A1",
)
print("  Default worksheet → 'Overview'")

# ── update backend/.env ───────────────────────────────────────────────────
if env_path.exists():
    env_text = env_path.read_text(encoding="utf-8")
    new_line  = f"GOOGLE_SPREADSHEET_ID={SPREADSHEET_ID}"
    pattern   = r"^GOOGLE_SPREADSHEET_ID=.*$"
    if re.search(pattern, env_text, re.MULTILINE):
        env_text = re.sub(pattern, new_line, env_text, flags=re.MULTILINE)
    else:
        env_text += f"\n{new_line}\n"
    env_path.write_text(env_text, encoding="utf-8")
    print(f"\n.env updated → GOOGLE_SPREADSHEET_ID={SPREADSHEET_ID}")

# ── final output ──────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("SUCCESS — Nai sheet ban gayi risingyeti00@gmail.com ke Drive mein!")
print("=" * 70)
print(f"\n📁 Google Drive Folder  : {FOLDER_LINK}")
print(f"📊 Google Spreadsheet   : {SPREADSHEET_LINK}")
print(f"👤 Owner                : {OWNER_EMAIL}")
if SA_EMAIL:
    print(f"🔑 Service Account      : {SA_EMAIL}")

print("\n" + "=" * 70)
print("Railway Dashboard mein ye 3 variables daalo:")
print("=" * 70)
print(f"\nGOOGLE_SPREADSHEET_ID={SPREADSHEET_ID}")
print(f"\nGOOGLE_SHEETS_SYNC_ENABLED=True")
if SA_JSON_ONE_LINE:
    print(f"\nGOOGLE_SERVICE_ACCOUNT_JSON={SA_JSON_ONE_LINE}")

print("\n" + "=" * 70)
print("Ab ye commands chalao (backend/ folder mein):")
print("=" * 70)
print("  python manage.py migrate sheets_sync")
print("  python manage.py sheets_check")
print("  python manage.py sheets_backfill")
print("\nFir Railway pe redeploy karo — live sync shuru ho jayega!")
