
#!/usr/bin/env python
import os
import django
import sys

# Add the project root directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

try:
    django.setup()
    print("Django setup successful!")
except Exception as e:
    print("Django setup failed:", e)
    import traceback
    print(traceback.format_exc())
    sys.exit(1)

from django.core.mail import send_mail
from django.conf import settings

print("\nEmail Configuration:")
print("EMAIL_HOST:", settings.EMAIL_HOST)
print("EMAIL_PORT:", settings.EMAIL_PORT)
print("EMAIL_HOST_USER:", settings.EMAIL_HOST_USER)
print("EMAIL_USE_TLS:", settings.EMAIL_USE_TLS)
print("DEFAULT_FROM_EMAIL:", settings.DEFAULT_FROM_EMAIL)
print("EMAIL_HOST_PASSWORD is set:", bool(settings.EMAIL_HOST_PASSWORD))

print("\nSending test email to", settings.EMAIL_HOST_USER)
try:
    result = send_mail(
        subject="FarmERP Test Email",
        message="This is a test email from your FarmERP backend! If you received this, email sending is working!",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[settings.EMAIL_HOST_USER],
        fail_silently=False,
    )
    print("\nSUCCESS! Test email sent! Result:", result)
    print("Check your inbox at", settings.EMAIL_HOST_USER)
except Exception as e:
    print("\nERROR sending test email:", type(e).__name__, str(e))
    import traceback
    print("\nStack trace:")
    print(traceback.format_exc())
