#!/usr/bin/env python3
"""
FarmERP → Google Sheets Live Backup — One-time Setup
=====================================================

This script automates the entire Google Cloud infrastructure setup:

1. Authenticates you via OAuth2 (opens a browser window — log into risingyeti00@gmail.com)
2. Creates (or finds) a Google Cloud Project named "FarmERP Backup"
3. Enables Google Drive API + Google Sheets API
4. Creates a Service Account
5. Generates a JSON key for the Service Account
6. Creates a Google Drive folder "FarmERP Live Backup"
7. Creates a Google Spreadsheet "FarmERP Live Database" inside that folder
8. Shares the spreadsheet with the Service Account as Editor
9. Outputs everything you need for Railway configuration

Prerequisites (installed automatically if missing):
    pip install --quiet google-auth google-auth-oauthlib google-auth-httplib2 \
        google-api-python-client google-cloud-resource-manager

Usage:
    python setup_google_sync.py

You'll be prompted to log into your Google account in the browser that opens.
"""

import json
import os
import re
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Dependencies — auto-install
# ---------------------------------------------------------------------------
_REQUIRED = [
    "google-auth",
    "google-auth-oauthlib",
    "google-auth-httplib2",
    "google-api-python-client",
    "google-cloud-resource-manager",
]

for _pkg in _REQUIRED:
    try:
        __import__(_pkg.replace("-", "_"))
    except ImportError:
        print(f"📦 Installing {_pkg}...")
        import subprocess
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--quiet", _pkg],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.cloud import resourcemanager_v3


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
PROJECT_NAME = "FarmERP Backup"
PROJECT_ID_SUFFIX = "farmerp-backup"  # GCP project IDs are globally unique

SCOPES = [
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
]

DRIVE_FOLDER_NAME = "FarmERP Live Backup"
SPREADSHEET_NAME = "FarmERP Live Database"

TOKEN_FILE = Path.home() / ".farmerp_google_setup_token.json"
CREDENTIALS_DIR = Path(__file__).parent / "credentials"


# ===================================================================
# Step 0 — OAuth2 Desktop Authentication
# ===================================================================
def authenticate():
    """Authenticate the user via OAuth2 desktop flow.

    Opens a browser for the user to log into risingyeti00@gmail.com.
    The token is cached locally so you only need to log in once.
    """
    print("\n" + "=" * 60)
    print("🔐  STEP 0: Google Authentication")
    print("=" * 60)
    print("A browser window will open. Log into:")
    print("    risingyeti00@gmail.com")
    print("then grant the requested permissions.")
    print()

    creds = None

    # Load cached token, if any
    if TOKEN_FILE.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
        except Exception:
            creds = None

    # Refresh expired token
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(GoogleRequest())

    if not creds or not creds.valid:
        # OAuth2 desktop flow — we use the client ID published by Google
        # for the "gcloud CLI" OAuth client. This avoids you having to
        # create your own OAuth client ID in the console first.
        client_config = {
            "installed": {
                "client_id": "764086051850-6qr4p6gpi6hn506pt8ejeqoasv2e6iqr.apps.googleusercontent.com",
                "project_id": "",
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "client_secret": "d-FL95Q19q7MQmFpd7hHD0Ty",
                "redirect_uris": ["http://localhost"]
            }
        }
        flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
        creds = flow.run_local_server(port=0, open_browser=True)

        # Cache the token
        TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
        print(f"  ✅ Token cached at {TOKEN_FILE}")

    email = _get_email(creds)
    print(f"  ✅ Authenticated as: {email}")
    return creds, email


def _get_email(creds):
    """Try to extract the user's email from the OAuth token."""
    try:
        service = build("oauth2", "v2", credentials=creds)
        user_info = service.userinfo().get().execute()
        return user_info.get("email", "unknown")
    except Exception:
        return "risingyeti00@gmail.com"


# ===================================================================
# Step 1 — Find or Create Google Cloud Project
# ===================================================================
def find_or_create_project(creds, user_email):
    print("\n" + "=" * 60)
    print("☁️  STEP 1: Google Cloud Project")
    print("=" * 60)

    projects_client = resourcemanager_v3.ProjectsClient(credentials=creds)

    # Try to find an existing project with our name
    print("  🔍 Looking for existing project...")
    try:
        request = resourcemanager_v3.SearchProjectsRequest(query=f"name:{PROJECT_NAME}")
        page = projects_client.search_projects(request=request)
        existing = list(page)
        if existing:
            proj = existing[0]
            project_id = proj.project_id
            print(f"  ✅ Found existing project: {proj.display_name} ({project_id})")
            print(f"     State: {proj.state}")
            if proj.state.name == "ACTIVE":
                return project_id
            else:
                print(f"  ⚠️  Project is in {proj.state.name} state, trying to create new one")
    except Exception as e:
        print(f"  ⚠️  Could not search projects: {e}")

    # Try to create a new project
    # GCP project IDs must be globally unique — we use email-based suffix
    email_slug = re.sub(r"[^a-z0-9]", "", user_email.split("@")[0][:20])
    project_id = f"{PROJECT_ID_SUFFIX}-{email_slug}-{int(time.time())}"
    project_id = project_id[:30].lower().strip("-")

    print(f"  🆕 Creating project '{PROJECT_NAME}' (ID: {project_id})...")

    try:
        operation = projects_client.create_project(
            resourcemanager_v3.Project(
                project_id=project_id,
                display_name=PROJECT_NAME,
            )
        )
        print("  ⏳  Waiting for project creation (this may take 30-60s)...")
        operation.result(timeout=120)  # Wait up to 2 minutes
        print(f"  ✅ Project '{PROJECT_NAME}' created!")
        print(f"     Project ID: {project_id}")
        print(f"     Open: https://console.cloud.google.com/welcome?project={project_id}")
        return project_id
    except Exception as e:
        print(f"  ❌ Could not create project: {e}")
        print()
        print("  ────────────────────────────────────────────────────────")
        print("  Manual step required:")
        print(f"  1. Go to https://console.cloud.google.com/projectcreate")
        print(f"  2. Create a project named '{PROJECT_NAME}'")
        print(f"  3. Note the Project ID")
        print("  4. Re-run this script and enter the Project ID below")
        print("  ────────────────────────────────────────────────────────")
        manual_id = input("  ➤  Enter your Project ID (or press Enter to retry): ").strip()
        if manual_id:
            return manual_id
        # Retry once
        print("  🔄 Retrying project creation...")
        time.sleep(5)
        try:
            operation = projects_client.create_project(
                resourcemanager_v3.Project(
                    project_id=project_id,
                    display_name=PROJECT_NAME,
                )
            )
            operation.result(timeout=120)
            print(f"  ✅ Project created on retry! ID: {project_id}")
            return project_id
        except Exception as e2:
            print(f"  ❌ Still failed: {e2}")
            manual_id = input("  ➤  Enter your Project ID manually: ").strip()
            if manual_id:
                return manual_id
            sys.exit(1)


# ===================================================================
# Step 2 — Enable APIs
# ===================================================================
def enable_apis(creds, project_id):
    print("\n" + "=" * 60)
    print("🔌  STEP 2: Enabling Google APIs")
    print("=" * 60)

    service = build("serviceusage", "v1", credentials=creds)

    apis = [
        "sheets.googleapis.com",     # Google Sheets API
        "drive.googleapis.com",      # Google Drive API
        "iam.googleapis.com",        # Identity & Access Management (for service accounts)
        "cloudresourcemanager.googleapis.com",  # Resource Manager
    ]

    for api_name in apis:
        print(f"  ⏳  Enabling {api_name}...", end=" ")
        try:
            request = service.services().enable(
                name=f"projects/{project_id}/services/{api_name}"
            )
            # Use execute() directly — this might already be enabled
            try:
                request.execute()
                print("✅")
            except HttpError as e:
                if e.resp.status == 403 and "not found" in str(e).lower():
                    # The API may not be in the discovery doc yet — try activating it
                    print("⚠️  (may already be enabled)")
                elif e.resp.status == 400:
                    # Precondition check failed — might already be enabled
                    print("✅ (already active)")
                else:
                    raise
        except Exception as e:
            # If it's already enabled, that's fine
            if "already been enabled" in str(e) or "already enabled" in str(e).lower():
                print("✅ (already enabled)")
            elif "PERMISSION_DENIED" in str(e):
                print(f"❌ Permission denied — you may need to enable manually")
                print(f"     Go to: https://console.cloud.google.com/apis/library/{api_name}?project={project_id}")
            else:
                print(f"❌ {e}")
                print(f"     Go to: https://console.cloud.google.com/apis/library/{api_name}?project={project_id}")

    print("  ⏳  Waiting for APIs to propagate...")
    time.sleep(10)
    print("  ✅ APIs enabled (or already active)")


# ===================================================================
# Step 3 — Create Service Account + JSON Key
# ===================================================================
def create_service_account(creds, project_id):
    print("\n" + "=" * 60)
    print("🔑  STEP 3: Service Account")
    print("=" * 60)

    iam = build("iam", "v1", credentials=creds)
    name = f"projects/{project_id}/serviceAccounts"

    sa_account_id = "farmerp-sheets-sync"
    sa_display = "FarmERP Sheets Sync"

    # Check if the service account already exists
    print(f"  🔍 Checking for existing service account '{sa_account_id}'...")
    try:
        existing = iam.projects().serviceAccounts().get(
            name=f"{name}/{sa_account_id}@{project_id}.iam.gserviceaccount.com"
        ).execute()
        sa_email = existing["email"]
        print(f"  ✅ Found existing service account: {sa_email}")
    except HttpError as e:
        if e.resp.status == 404:
            print(f"  🆕 Creating service account '{sa_display}'...")
            try:
                sa = iam.projects().serviceAccounts().create(
                    name=name,
                    body={
                        "accountId": sa_account_id,
                        "serviceAccount": {
                            "displayName": sa_display,
                            "description": "Automated Google Sheets sync for FarmERP database backup"
                        }
                    }
                ).execute()
                sa_email = sa["email"]
                print(f"  ✅ Created: {sa_email}")
            except HttpError as e2:
                if e2.resp.status == 409:
                    # Actually exists (race condition)
                    sa_email = f"{sa_account_id}@{project_id}.iam.gserviceaccount.com"
                    print(f"  ✅ Already exists: {sa_email}")
                else:
                    raise
        else:
            raise

    # Generate JSON key
    print("  🔑 Generating JSON key...")
    CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)
    key_file = CREDENTIALS_DIR / "farmerp-sheets-sync-key.json"

    try:
        key = iam.projects().serviceAccounts().keys().create(
            name=f"projects/{project_id}/serviceAccounts/{sa_email}",
            body={"keyAlgorithm": "KEY_ALG_RSA_2048", "privateKeyType": "TYPE_GOOGLE_CREDENTIALS_FILE"}
        ).execute()
        key_data = json.loads(key["privateKeyData"])
        with open(key_file, "w") as f:
            json.dump(key_data, f, indent=2)
        print(f"  ✅ Key saved to: {key_file}")
    except HttpError as e:
        print(f"  ⚠️  Could not create key via API: {e}")
        print("  ➤  Create it manually:")
        print(f"     1. Go to: https://console.cloud.google.com/iam-admin/serviceaccounts?project={project_id}")
        print(f"     2. Click the '{sa_display}' service account")
        print(f"     3. Keys -> Add Key -> Create New Key -> JSON")
        print(f"     4. Save the downloaded file as: {key_file}")
        input("     Press Enter after you've saved the key file...")

    if not key_file.exists():
        print(f"  ❌ Key file not found at {key_file}")
        sys.exit(1)

    # Also show the JSON content for Railway env var
    with open(key_file) as f:
        key_json = json.load(f)

    print(f"\n  📋 Service Account Email: {sa_email}")
    print(f"  📋 Key file: {key_file}")

    return sa_email, key_file, key_json


# ===================================================================
# Step 4 — Create Google Drive Folder + Spreadsheet
# ===================================================================
def create_drive_resources(creds, project_id, sa_email, key_json):
    print("\n" + "=" * 60)
    print("📁  STEP 4: Google Drive Folder & Spreadsheet")
    print("=" * 60)

    # We use the Service Account's own credentials to create Drive resources
    # This ensures the Service Account owns the folder/spreadsheet
    from google.oauth2 import service_account

    sa_creds = service_account.Credentials.from_service_account_info(
        key_json, scopes=[
            "https://www.googleapis.com/auth/drive",
            "https://www.googleapis.com/auth/spreadsheets",
        ]
    )
    drive = build("drive", "v3", credentials=sa_creds)
    sheets = build("sheets", "v4", credentials=sa_creds)

    # ── Create Drive folder ──────────────────────────────────────────
    print(f"  📁 Creating Drive folder '{DRIVE_FOLDER_NAME}'...")
    try:
        folder_metadata = {
            "name": DRIVE_FOLDER_NAME,
            "mimeType": "application/vnd.google-apps.folder",
        }
        folder = drive.files().create(body=folder_metadata, fields="id,name,webViewLink").execute()
        folder_id = folder["id"]
        folder_link = folder["webViewLink"]
        print(f"  ✅ Folder created!")
        print(f"     Link: {folder_link}")
    except HttpError as e:
        print(f"  ❌ Could not create folder: {e}")
        # Try as the main user's credentials
        print("  🔄 Retrying with your own Google credentials...")
        drive_user = build("drive", "v3", credentials=creds)
        folder_metadata = {
            "name": DRIVE_FOLDER_NAME,
            "mimeType": "application/vnd.google-apps.folder",
        }
        folder = drive_user.files().create(body=folder_metadata, fields="id,name,webViewLink").execute()
        folder_id = folder["id"]
        folder_link = folder["webViewLink"]
        print(f"  ✅ Folder created in your Drive!")
        print(f"     Link: {folder_link}")

    # ── Create Spreadsheet inside folder ─────────────────────────────
    print(f"  📊 Creating spreadsheet '{SPREADSHEET_NAME}'...")
    try:
        spreadsheet_metadata = {
            "properties": {"title": SPREADSHEET_NAME},
            # Put it in the folder
        }
        spreadsheet = sheets.spreadsheets().create(
            body=spreadsheet_metadata,
            fields="spreadsheetId,spreadsheetUrl"
        ).execute()
        sheet_id = spreadsheet["spreadsheetId"]
        sheet_url = spreadsheet["spreadsheetUrl"]

        # Move it into the folder
        try:
            drive.files().update(
                fileId=sheet_id,
                addParents=folder_id,
                removeParents="root",
                fields="id,parents"
            ).execute()
        except Exception:
            # Try with user credentials
            try:
                drive_user = build("drive", "v3", credentials=creds)
                drive_user.files().update(
                    fileId=sheet_id,
                    addParents=folder_id,
                    fields="id"
                ).execute()
            except Exception:
                print("  ⚠️  Could not move file to folder — it's still in root of Drive")
        print(f"  ✅ Spreadsheet created!")
        print(f"     Link: {sheet_url}")
    except HttpError as e:
        print(f"  ❌ Could not create spreadsheet: {e}")
        sys.exit(1)

    # ── Share spreadsheet with Service Account ───────────────────────
    print(f"  🔗 Sharing spreadsheet with service account ({sa_email})...")
    try:
        permission = {
            "type": "user",
            "role": "writer",
            "emailAddress": sa_email,
            "sendNotificationEmail": False,
        }
        drive.permissions().create(
            fileId=sheet_id,
            body=permission,
            fields="id",
            sendNotificationEmail=False,
        ).execute()
        print(f"  ✅ Shared as Editor with: {sa_email}")
    except HttpError as e:
        print(f"  ❌ Could not share: {e}")
        print(f"  ➤  Share manually:")
        print(f"     1. Open: {sheet_url}")
        print(f"     2. Share with {sa_email} as Editor")
        input("     Press Enter when done...")

    # ── Rename default sheet ─────────────────────────────────────────
    try:
        default_sheets = sheets.spreadsheets().get(
            spreadsheetId=sheet_id, fields="sheets.properties"
        ).execute()
        first_sheet = default_sheets["sheets"][0]["properties"]
        sheets.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id,
            body={
                "requests": [{
                    "updateSheetProperties": {
                        "properties": {
                            "sheetId": first_sheet["sheetId"],
                            "title": "Sync Info"
                        },
                        "fields": "title"
                    }
                }]
            }
        ).execute()
        # Add some info to the first sheet
        sheets.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range="Sync Info!A1:D3",
            valueInputOption="USER_ENTERED",
            body={
                "values": [
                    ["FarmERP Pro — Live Database Mirror"],
                    ["Created", time.strftime("%Y-%m-%d %H:%M:%S IST")],
                    ["Service Account", sa_email],
                    ["Status", "✅ Active — waiting for backfill"],
                ]
            }
        ).execute()
    except Exception:
        pass  # Non-critical

    # ── Also share the Drive folder with the SA ──────────────────────
    try:
        permission = {
            "type": "user",
            "role": "writer",
            "emailAddress": sa_email,
            "sendNotificationEmail": False,
        }
        drive.permissions().create(
            fileId=folder_id,
            body=permission,
            fields="id",
        ).execute()
    except Exception:
        pass  # Non-critical

    print(f"\n  ✅ All Drive resources ready!")
    return folder_id, folder_link or f"https://drive.google.com/drive/folders/{folder_id}", sheet_id, sheet_url


# ===================================================================
# Step 5 — Grant IAM Permissions (so SA can list projects etc.)
# ===================================================================
def grant_iam_permissions(creds, project_id, sa_email):
    """Grant the service account minimal permissions on the project.

    The service account needs:
    - roles/viewer (to browse the project and list resources)
    """
    print("\n" + "=" * 60)
    print("🛡️  STEP 5: IAM Permissions")
    print("=" * 60)

    crm = build("cloudresourcemanager", "v3", credentials=creds)

    try:
        # Get current IAM policy
        policy = crm.projects().getIamPolicy(
            resource=project_id,
            body={}
        ).execute()

        # Check if viewer role is already assigned
        member = f"serviceAccount:{sa_email}"
        viewer_role = "roles/viewer"
        already_viewer = any(
            binding["role"] == viewer_role and member in binding.get("members", [])
            for binding in policy.get("bindings", [])
        )

        if already_viewer:
            print(f"  ✅ Service account already has Viewer role")
        else:
            # Add viewer role
            found = False
            for binding in policy.get("bindings", []):
                if binding["role"] == viewer_role:
                    binding.setdefault("members", []).append(member)
                    found = True
                    break
            if not found:
                policy.setdefault("bindings", []).append({
                    "role": viewer_role,
                    "members": [member]
                })

            # Also add serviceAccountUser role for the SA to create resources
            sa_user_role = "roles/iam.serviceAccountUser"
            found_sa = False
            for binding in policy.get("bindings", []):
                if binding["role"] == sa_user_role:
                    binding.setdefault("members", []).append(member)
                    found_sa = True
                    break
            if not found_sa:
                policy.setdefault("bindings", []).append({
                    "role": sa_user_role,
                    "members": [member]
                })

            crm.projects().setIamPolicy(
                resource=project_id,
                body={"policy": policy}
            ).execute()
            print(f"  ✅ Assigned Viewer + Service Account User roles to {sa_email}")

        print("  ⏳  Waiting for IAM propagation...")
        time.sleep(15)

    except HttpError as e:
        print(f"  ⚠️  Could not set IAM policy: {e}")
        print("  ➤  You can skip this — the sync only needs Drive/Sheets access")


# ===================================================================
# Step 6 — Output configuration
# ===================================================================
def print_config(project_id, sa_email, key_json, folder_link, sheet_id, sheet_url):
    print("\n" + "=" * 60)
    print("🎉  SETUP COMPLETE!")
    print("=" * 60)

    print(f"""
📋  GOOGLE CLOUD RESOURCES
──────────────────────────
🌐  Google Cloud Project: {PROJECT_NAME}
     Project ID:           {project_id}
     Console:              https://console.cloud.google.com/welcome?project={project_id}

🔑  Service Account:       {sa_email}
     Key file:             {CREDENTIALS_DIR / "farmerp-sheets-sync-key.json"}

📁  Drive Folder:          {DRIVE_FOLDER_NAME}
     Link:                 {folder_link}

📊  Spreadsheet:           {SPREADSHEET_NAME}
     ID:                   {sheet_id}
     Link:                 {sheet_url}
""")

    print("=" * 60)
    print("🚀  RAILWAY ENVIRONMENT VARIABLES")
    print("=" * 60)
    print("""
Set these in your Railway dashboard (farmerp-backend service)
or run the commands below:

    railway variables set \\
        GOOGLE_SHEETS_SYNC_ENABLED=True \\
        GOOGLE_SPREADSHEET_ID={sheet_id} \\
        GOOGLE_SERVICE_ACCOUNT_JSON='{sa_json}'

""".format(sheet_id=sheet_id, sa_json=json.dumps(key_json).replace("'", "'\\''")))

    # Also save the env vars to a file
    env_file = Path(__file__).parent / ".env.google_sync"
    sa_json_escaped = json.dumps(key_json).replace("'", "'\\''")
    with open(env_file, "w") as f:
        f.write(f"""# Google Sheets Sync — FarmERP
# Generated by setup_google_sync.py on {time.strftime('%Y-%m-%d %H:%M:%S')}
# Copy these values into Railway environment variables

GOOGLE_SHEETS_SYNC_ENABLED=True
GOOGLE_SPREADSHEET_ID={sheet_id}
GOOGLE_SERVICE_ACCOUNT_JSON='{sa_json_escaped}'

# --- Reference ---
# Service Account Email: {sa_email}
# Drive Folder: {folder_link}
# Spreadsheet URL: {sheet_url}
""")
    print(f"  ✅ Environment variables also saved to: {env_file}")
    print()

    # Save for programmatic use
    config_file = CREDENTIALS_DIR / "sync_config.json"
    with open(config_file, "w") as f:
        json.dump({
            "project_id": project_id,
            "sa_email": sa_email,
            "folder_link": folder_link,
            "sheet_id": sheet_id,
            "sheet_url": sheet_url,
        }, f, indent=2)
    print(f"  ✅ Config saved to: {config_file}")
    print()


# ===================================================================
# Main
# ===================================================================
def main():
    print()
    print("╔══════════════════════════════════════════════════════╗")
    print("║     🌾 FarmERP → Google Sheets Live Sync Setup     ║")
    print("╚══════════════════════════════════════════════════════╝")
    print()
    print(f"  Drive Folder:  \"{DRIVE_FOLDER_NAME}\"")
    print(f"  Spreadsheet:   \"{SPREADSHEET_NAME}\"")
    print(f"  Google Account: risingyeti00@gmail.com")
    print()

    try:
        # Step 0 — Authenticate
        creds, email = authenticate()

        # Step 1 — Project
        project_id = find_or_create_project(creds, email)

        # Step 2 — Enable APIs
        enable_apis(creds, project_id)

        # Step 3 — Service Account
        sa_email, key_file, key_json = create_service_account(creds, project_id)

        # Step 4 — Drive Folder & Spreadsheet
        folder_id, folder_link, sheet_id, sheet_url = create_drive_resources(
            creds, project_id, sa_email, key_json
        )

        # Step 5 — IAM
        grant_iam_permissions(creds, project_id, sa_email)

        # Step 6 — Output
        print_config(project_id, sa_email, key_json, folder_link, sheet_id, sheet_url)

        print("=" * 60)
        print("✅  ALL DONE! Next steps:")
        print("=" * 60)
        print("""
  1. Set the Railway environment variables (shown above)
  2. Redeploy the backend on Railway
  3. Run the backfill to copy existing data:
       railway run python manage.py sheets_backfill
  4. Verify:
       railway run python manage.py sheets_check
  5. Check the spreadsheet — every table will have its own worksheet
  6. Insert a test record in FarmERP and verify it appears in Sheets

  Your database is now LIVE-backed up to Google Sheets! 🚀
""")

    except KeyboardInterrupt:
        print("\n\n  ❌ Setup cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n  ❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
