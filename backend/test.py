
print("Hello from test.py!")
import os
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent
print("BASE_DIR:", BASE_DIR)
print(".env exists:", (BASE_DIR / ".env").exists())
from dotenv import load_dotenv
load_dotenv(BASE_DIR / ".env")
print("EMAIL_HOST_USER:", os.getenv("EMAIL_HOST_USER"))
print("EMAIL_HOST_PASSWORD:", bool(os.getenv("EMAIL_HOST_PASSWORD")))
