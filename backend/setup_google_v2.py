#!/usr/bin/env python3
"""
FarmERP -> Google Sheets Live Backup Setup
===========================================
Automates: Google Cloud project, APIs, Service Account, Drive folder,
Spreadsheet sharing, and Railway env vars.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

# Auto-install dependencies
_REQUIRED_PKGS = [
    "google-auth",
    "google-auth-oauthlib",
    "google-auth-httplib2",
    "google-api-python-client",
    "google-cloud-resource-manager",
]
for _pkg in _REQUIRED_PKGS:
    try:
        if _pkg == "google-auth":
            import google.auth  # noqa
        elif _pkg == "google-auth-oauthlib":
            import google_auth_oauthlib  # noqa
        elif _pkg == "google-auth-httplib2":
            import google_auth_httplib2  # noqa
        elif _pkg == "google-api-python-client":
            import googleapiclient  # noqa
        elif _pkg == "google-cloud-resource-manager":
            from google.cloud import resourcemanager_v3  # noqa
    except ImportError:
        print("Installing " + _pkg + "...")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--quiet", _pkg],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )

from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = [
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
]

TOKEN_FILE = Path.home() / ".farmerp_google_token.json"
CREDENTIALS_DIR = Path(__file__).parent / "credentials"
DRIVE_FOLDER_NAME = "FarmERP Live Backup"
SPREADSHEET_NAME = "FarmERP Live Database"
SPREADSHEET_ID = "1010Qr316QWW7TpCBx9hCR5Eu5nQQDhgSrU-Ddwg9WtE"

CLIENT_CONFIG = {
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


def authenticate():
    print()
    print("=" * 60)
    print("STEP 1 - AUTHENTICATION")
    print("=" * 60)
    print("A browser window will open.")
    print("Log into: risingyeti00@gmail.com")
    print("Then grant the requested permissions.")
    print()

    creds = None
    if TOKEN_FILE.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
        except Exception:
            creds = None

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(GoogleRequest())

    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_config(CLIENT_CONFIG, SCOPES)
        creds = flow.run_local_server(port=0, open_browser=True)
        TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
        print("  Token cached at " + str(TOKEN_FILE))

    print("  Authenticated!")
    return creds


def get_project_id(creds):
    """Find or create a GCP project."""
    print()
    print("=" * 60)
    print("STEP 2 - GOOGLE CLOUD PROJECT")
    print("=" * 60)

    # Try to find existing projects
    try:
        crm_v1 = build("cloudresourcemanager", "v1", credentials=creds)
        print("  Searching for existing projects...")
        projects = crm_v1.projects().list().execute().get("projects", [])
        for proj in projects:
            pid = proj.get("projectId", "")
            if proj.get("lifecycleState") == "ACTIVE":
                print("  Using existing project: " + proj.get("name", pid) + " (" + pid + ")")
                return pid
    except Exception as e:
        print("  Could not list projects: " + str(e))

    # Create a new project
    print("  Creating new project 'FarmERP Backup'...")
    project_id = "farmerp-backup-" + str(int(time.time()))

    try:
        from google.cloud import resourcemanager_v3
        client = resourcemanager_v3.ProjectsClient(credentials=creds)
        operation = client.create_project(
            resourcemanager_v3.Project(
                project_id=project_id,
                display_name="FarmERP Backup",
            )
        )
        print("  Waiting for project creation (up to 2 min)...")
        operation.result(timeout=120)
        print("  Created project: " + project_id)
        time.sleep(10)
        return project_id
    except Exception as e:
        print("  Project creation failed: " + str(e))
        print()
        print("  -- Manual step required --")
        print("  1. Open: https://console.cloud.google.com/projectcreate")
        print("  2. Project name: FarmERP Backup")
        print("  3. Click CREATE")
        print("  4. Wait 10 seconds, then press Enter")
        print("  ---------------------------")
        input("  Press Enter after creating the project... ")

        # Try to list projects again
        try:
            crm_v1 = build("cloudresourcemanager", "v1", credentials=creds)
            projects = crm_v1.projects().list().execute().get("projects", [])
            for proj in projects:
                pid = proj.get("projectId", "")
                if proj.get("lifecycleState") == "ACTIVE" and "farmerp" in pid:
                    print("  Using project: " + pid)
                    return pid
        except Exception:
            pass

        manual = input("  Enter the Project ID from console: ").strip()
        if manual:
            return manual
        sys.exit(1)


def enable_apis(creds, project_id):
    """Enable required APIs."""
    print()
    print("=" * 60)
    print("STEP 3 - ENABLING APIs")
    print("=" * 60)

    service = build("serviceusage", "v1", credentials=creds)
    apis = [
        "sheets.googleapis.com",
        "drive.googleapis.com",
        "iam.googleapis.com",
        "cloudresourcemanager.googleapis.com",
    ]

    for api in apis:
        print("  Enabling " + api + "...", end=" ", flush=True)
        try:
            service.services().enable(
                name="projects/" + project_id + "/services/" + api
            ).execute()
            print("OK")
        except Exception as e:
            print("retrying...")
            time.sleep(3)
            try:
                service.services().enable(
                    name="projects/" + project_id + "/services/" + api
                ).execute()
                print("  OK")
            except Exception:
                print("  Could not enable " + api + " - continuing anyway")

    print("  Waiting for APIs to propagate...")
    time.sleep(15)
    print("  APIs ready!")


def create_service_account(creds, project_id):
    """Create service account and generate JSON key."""
    print()
    print("=" * 60)
    print("STEP 4 - SERVICE ACCOUNT")
    print("=" * 60)

    iam = build("iam", "v1", credentials=creds)
    sa_account_id = "farmerp-sheets-sync"
    sa_email = sa_account_id + "@" + project_id + ".iam.gserviceaccount.com"

    # Check if exists
    try:
        iam.projects().serviceAccounts().get(
            name="projects/" + project_id + "/serviceAccounts/" + sa_email
        ).execute()
        print("  Service account already exists: " + sa_email)
    except HttpError as e:
        if e.resp.status == 404:
            print("  Creating service account...")
            iam.projects().serviceAccounts().create(
                name="projects/" + project_id + "/serviceAccounts",
                body={
                    "accountId": sa_account_id,
                    "serviceAccount": {
                        "displayName": "FarmERP Sheets Sync",
                        "description": "Live sync FarmERP database to Google Sheets"
                    }
                }
            ).execute()
            print("  Created: " + sa_email)
        else:
            raise

    # Generate JSON key
    CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)
    key_file = CREDENTIALS_DIR / "farmerp-sheets-sync-key.json"

    try:
        key = iam.projects().serviceAccounts().keys().create(
            name="projects/" + project_id + "/serviceAccounts/" + sa_email,
            body={
                "keyAlgorithm": "KEY_ALG_RSA_2048",
                "privateKeyType": "TYPE_GOOGLE_CREDENTIALS_FILE"
            }
        ).execute()
        key_data = json.loads(key["privateKeyData"])
        with open(key_file, "w") as f:
            json.dump(key_data, f, indent=2)
        print("  Key saved to: " + str(key_file))
    except Exception as e:
        print("  Key generation failed: " + str(e))
        print("  Create key manually:")
        print("    1. https://console.cloud.google.com/iam-admin/serviceaccounts?project=" + project_id)
        print("    2. Click farmerp-sheets-sync -> Keys -> Add Key -> Create New Key -> JSON")
        print("    3. Save the file")
        key_path = input("  Path to downloaded JSON key file: ").strip()
        if key_path and os.path.exists(key_path):
            with open(key_path) as f:
                key_data = json.load(f)
            with open(key_file, "w") as f:
                json.dump(key_data, f, indent=2)
            print("  Key copied to: " + str(key_file))
        else:
            print("  Paste the ENTIRE JSON content below:")
            raw_lines = []
            print("  (paste line by line, type 'DONE' on a new line when finished)")
            while True:
                line = input()
                if line.strip() == "DONE":
                    break
                raw_lines.append(line)
            raw = "".join(raw_lines)
            try:
                key_data = json.loads(raw)
                with open(key_file, "w") as f:
                    json.dump(key_data, f, indent=2)
                print("  Key saved!")
            except json.JSONDecodeError:
                print("  Invalid JSON. Exiting.")
                sys.exit(1)

    return sa_email, key_file, key_data


def setup_drive_sheet(creds, sa_email, key_data):
    """Create Drive folder, share spreadsheet with SA."""
    print()
    print("=" * 60)
    print("STEP 5 - DRIVE FOLDER & SPREADSHEET")
    print("=" * 60)

    from google.oauth2 import service_account

    # Authenticate as service account first
    sa_creds = service_account.Credentials.from_service_account_info(
        key_data, scopes=[
            "https://www.googleapis.com/auth/drive",
            "https://www.googleapis.com/auth/spreadsheets",
        ]
    )
    drive_sa = build("drive", "v3", credentials=sa_creds)
    sheets_sa = build("sheets", "v4", credentials=sa_creds)

    folder_link = ""
    folder_id = ""

    print("  Creating folder '" + DRIVE_FOLDER_NAME + "'...")
    try:
        folder = drive_sa.files().create(
            body={"name": DRIVE_FOLDER_NAME, "mimeType": "application/vnd.google-apps.folder"},
            fields="id,webViewLink"
        ).execute()
        folder_id = folder["id"]
        folder_link = folder["webViewLink"]
        print("  Folder: " + folder_link)

        # Share with user
        drive_sa.permissions().create(
            fileId=folder_id,
            body={"type": "user", "role": "writer", "emailAddress": "risingyeti00@gmail.com"},
            fields="id"
        ).execute()
        print("  Folder shared with risingyeti00@gmail.com")
    except Exception as e:
        print("  Could not create folder with SA: " + str(e))
        print("  Creating folder with your account...")
        drive_user = build("drive", "v3", credentials=creds)
        folder = drive_user.files().create(
            body={"name": DRIVE_FOLDER_NAME, "mimeType": "application/vnd.google-apps.folder"},
            fields="id,webViewLink"
        ).execute()
        folder_id = folder["id"]
        folder_link = folder["webViewLink"]
        print("  Folder: " + folder_link)

    # Use existing spreadsheet
    sheet_id = SPREADSHEET_ID
    print("  Spreadsheet ID: " + sheet_id)

    # Move into folder
    try:
        drive_user = build("drive", "v3", credentials=creds)
        drive_user.files().update(
            fileId=sheet_id,
            addParents=folder_id,
            fields="id"
        ).execute()
        print("  Moved into folder")
    except Exception as e:
        print("  Note: could not move into folder - " + str(e))

    # Share spreadsheet with service account
    print("  Sharing with service account: " + sa_email)
    try:
        drive_user = build("drive", "v3", credentials=creds)
        drive_user.permissions().create(
            fileId=sheet_id,
            body={"type": "user", "role": "writer", "emailAddress": sa_email},
            fields="id"
        ).execute()
        print("  Shared as Editor!")
    except Exception as e:
        print("  Share failed: " + str(e))
        print("  Open the sheet and share manually:")
        print("    https://docs.google.com/spreadsheets/d/" + sheet_id + "/edit")
        print("    Add " + sa_email + " as Editor")
        input("  Press Enter when done... ")

    return folder_link or ("https://drive.google.com/drive/folders/" + folder_id), sheet_id


def set_railway_env(project_id, sa_email, key_data, sheet_id):
    """Set Railway environment variables."""
    print()
    print("=" * 60)
    print("STEP 6 - RAILWAY ENVIRONMENT VARIABLES")
    print("=" * 60)

    sa_json_str = json.dumps(key_data)
    env_file = Path(__file__).parent / ".env"

    try:
        result = subprocess.run(
            ["railway", "whoami"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            print("  Railway CLI connected")

            env_vars = [
                ("GOOGLE_SHEETS_SYNC_ENABLED", "True"),
                ("GOOGLE_SPREADSHEET_ID", sheet_id),
                ("GOOGLE_SERVICE_ACCOUNT_JSON", sa_json_str),
            ]
            for key, val in env_vars:
                proc = subprocess.run(
                    ["railway", "variables", "set", key + "=" + val],
                    capture_output=True, text=True, timeout=30
                )
                if proc.returncode == 0:
                    print("  Set " + key)
                else:
                    print("  Error setting " + key + ": " + proc.stderr[:200])

            print("  Env vars set! Redeploying...")
            subprocess.run(
                ["railway", "up", "--service", "farmerp-backend", "--detach"],
                capture_output=True, text=True, timeout=120
            )
            print("  Redeploy started!")
            return True
    except Exception as e:
        print("  Railway CLI error: " + str(e))

    # Fallback
    print("  Could not set Railway vars automatically.")
    print("  Set these in Railway dashboard:")
    print()
    print("    GOOGLE_SHEETS_SYNC_ENABLED = True")
    print("    GOOGLE_SPREADSHEET_ID = " + sheet_id)
    print("    GOOGLE_SERVICE_ACCOUNT_JSON = " + sa_json_str)
    print()

    env_content = (
        "# Google Sheets Sync - FarmERP\n"
        "# Copy these into Railway Environment Variables\n\n"
        "GOOGLE_SHEETS_SYNC_ENABLED=True\n"
        "GOOGLE_SPREADSHEET_ID=" + sheet_id + "\n"
        "GOOGLE_SERVICE_ACCOUNT_JSON='" + sa_json_str + "'\n"
    )
    with open(env_file, "w") as f:
        f.write(env_content)
    print("  Config saved to: " + str(env_file))
    return False


def print_summary(project_id, sa_email, folder_link, sheet_id):
    """Print final summary."""
    sheet_url = "https://docs.google.com/spreadsheets/d/" + sheet_id + "/edit"

    print()
    print("=" * 60)
    print("SETUP COMPLETE!")
    print("=" * 60)
    print()
    print("  Project ID:        " + project_id)
    print("  Service Account:   " + sa_email)
    print("  Drive Folder:      " + folder_link)
    print("  Spreadsheet:       " + sheet_url)
    print("  Spreadsheet ID:    " + sheet_id)
    print()
    print("  Key file:          " + str(CREDENTIALS_DIR / "farmerp-sheets-sync-key.json"))
    print()


def main():
    print("=" * 60)
    print("  FarmERP -> Google Sheets Live Backup Setup")
    print("=" * 60)

    try:
        creds = authenticate()
        project_id = get_project_id(creds)
        enable_apis(creds, project_id)
        sa_email, key_file, key_data = create_service_account(creds, project_id)
        folder_link, sheet_id = setup_drive_sheet(creds, sa_email, key_data)
        railway_ok = set_railway_env(project_id, sa_email, key_data, sheet_id)
        print_summary(project_id, sa_email, folder_link, sheet_id)

        if not railway_ok:
            print()
            print("  Railway vars were NOT set automatically.")
            print("  Please copy the config above and paste in Railway dashboard.")
            print("  Then run: railway up --service farmerp-backend --detach")
    except KeyboardInterrupt:
        print("\n  Cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print("\n  Error: " + str(e))
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
