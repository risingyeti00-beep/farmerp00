
#!/usr/bin/env python
import os
import django
import sys
import smtplib
import ssl
from email.mime.text import MIMEText

# Add the project root directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

print("Step 1: Loading environment...")
try:
    django.setup()
    print("Django setup successful!")
except Exception as e:
    print("Django setup failed:", e)
    import traceback
    print(traceback.format_exc())
    sys.exit(1)

from django.conf import settings

print("\nStep 2: Email Configuration:")
print("EMAIL_HOST:", settings.EMAIL_HOST)
print("EMAIL_PORT:", settings.EMAIL_PORT)
print("EMAIL_HOST_USER:", settings.EMAIL_HOST_USER)
print("EMAIL_USE_TLS:", settings.EMAIL_USE_TLS)
print("DEFAULT_FROM_EMAIL:", settings.DEFAULT_FROM_EMAIL)
print("EMAIL_HOST_PASSWORD is set:", bool(settings.EMAIL_HOST_PASSWORD))
print("EMAIL_HOST_PASSWORD length:", len(settings.EMAIL_HOST_PASSWORD))

print("\nStep 3: Testing raw SMTP connection (without Django)...")
try:
    context = ssl.create_default_context()
    print("Connecting to SMTP server...")
    with smtplib.SMTP(settings.EMAIL_HOST, settings.EMAIL_PORT, timeout=30) as server:
        print("Connected! Starting TLS...")
        server.starttls(context=context)
        print("TLS started! Logging in...")
        server.login(settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD)
        print("Logged in successfully!")
        
        # Create email message
        msg = MIMEText("This is a test email from raw SMTP!")
        msg['Subject'] = "FarmERP Raw SMTP Test"
        msg['From'] = settings.DEFAULT_FROM_EMAIL
        msg['To'] = settings.EMAIL_HOST_USER
        
        print("Sending email...")
        server.sendmail(settings.DEFAULT_FROM_EMAIL, [settings.EMAIL_HOST_USER], msg.as_string())
        print("SUCCESS: Raw SMTP email sent!")
        
except Exception as e:
    print("\nERROR in raw SMTP test:", type(e).__name__, str(e))
    import traceback
    print("\nStack trace:")
    print(traceback.format_exc())

print("\nStep 4: Testing Django send_mail...")
try:
    from django.core.mail import send_mail
    result = send_mail(
        subject="FarmERP Django Test Email",
        message="This is a test email from Django send_mail!",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[settings.EMAIL_HOST_USER],
        fail_silently=False,
    )
    print("\nSUCCESS! Django email sent! Result:", result)
    print("Check your inbox at", settings.EMAIL_HOST_USER)
except Exception as e:
    print("\nERROR sending Django email:", type(e).__name__, str(e))
    import traceback
    print("\nStack trace:")
    print(traceback.format_exc())
