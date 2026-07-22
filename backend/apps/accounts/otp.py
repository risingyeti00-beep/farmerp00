import secrets
import string
from datetime import timedelta

from django.contrib.auth.hashers import check_password, make_password
from django.utils import timezone
from django.db import models


class OTP(models.Model):
    """Stores OTP codes for authentication (phone or email based).

    For LOGIN purpose: code is stored in plaintext for backward compatibility.
    For PASSWORD_RESET purpose: code is hashed via Django's PBKDF2 hasher.
    """

    # Generic identifier field that can hold either phone number OR email
    identifier = models.CharField(max_length=255, db_index=True)
    code = models.CharField(max_length=6, blank=True, default="")
    # Hashed OTP for PASSWORD_RESET; null/empty for LOGIN (uses plain `code`)
    # nullable=True for backward compatibility with OTPs created by older code
    hashed_code = models.CharField(max_length=128, blank=True, null=True, default=None)
    purpose = models.CharField(max_length=20, default="LOGIN")  # LOGIN, PASSWORD_RESET
    is_used = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"OTP for {self.identifier} ({'used' if self.is_used else 'active'})"

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    @property
    def is_valid(self):
        return not self.is_used and not self.is_expired

    @classmethod
    def generate(cls, identifier, purpose="LOGIN", expiry_minutes=5):
        """Generate a new OTP, invalidating previous unused ones.

        Returns (otp_instance, plaintext_code). For PASSWORD_RESET the code
        is hashed before storage; for LOGIN it is stored in plaintext.
        """
        # Invalidate previous unused OTPs for this identifier+purpose
        cls.objects.filter(
            identifier=identifier, purpose=purpose, is_used=False
        ).update(is_used=True)

        code = "".join(secrets.choice(string.digits) for _ in range(6))
        now = timezone.now()

        kwargs = {
            "identifier": identifier,
            "purpose": purpose,
            "created_at": now,
            "expires_at": now + timedelta(minutes=expiry_minutes),
        }

        if purpose == "PASSWORD_RESET":
            # Store hashed OTP — plaintext code is NOT persisted for security
            kwargs["hashed_code"] = make_password(code)
            kwargs["code"] = ""
        else:
            # LOGIN keeps plaintext for backward compatibility
            kwargs["code"] = code

        otp = cls.objects.create(**kwargs)
        return otp, code

    @classmethod
    def _match_otp(cls, identifier, code, purpose="LOGIN"):
        """Find the active (unused, not expired) OTP for this identifier/purpose
        and verify the provided code against it.

        Returns the matched OTP instance or None.
        """
        otp = cls.objects.filter(
            identifier=identifier, purpose=purpose, is_used=False
        ).first()

        if otp is None:
            return None
        if otp.is_expired:
            return None

        if purpose == "PASSWORD_RESET" and otp.hashed_code:
            if not check_password(code, otp.hashed_code):
                return None
        elif purpose == "LOGIN":
            if otp.code != code:
                return None
        else:
            return None

        return otp

    @classmethod
    def peek(cls, identifier, code, purpose="LOGIN"):
        """Validate an OTP WITHOUT consuming it. Returns (valid, reason).

        NB: named ``peek`` rather than ``check`` on purpose — Django's system
        check framework calls ``Model.check(**kwargs)``, so a classmethod named
        ``check`` here would shadow it and break ``manage.py check``/startup.

        reason is one of: None (valid), "invalid" (no such active code),
        "expired" (matched but past the expiry window).
        """
        otp = cls.objects.filter(
            identifier=identifier, purpose=purpose, is_used=False
        ).first()
        if otp is None:
            return False, "invalid"
        if otp.is_expired:
            return False, "expired"

        if purpose == "PASSWORD_RESET" and otp.hashed_code:
            if not check_password(code, otp.hashed_code):
                return False, "invalid"
        elif purpose == "LOGIN":
            if otp.code != code:
                return False, "invalid"
        else:
            return False, "invalid"

        return True, None

    @classmethod
    def verify(cls, identifier, code, purpose="LOGIN"):
        """Verify an OTP and CONSUME it (single use). Returns (success, otp)."""
        otp = cls._match_otp(identifier, code, purpose)

        if otp is None:
            return False, None

        otp.is_used = True
        otp.save(update_fields=["is_used"])
        return True, otp

    @classmethod
    def verify_for_reset(cls, identifier, code):
        """Verify a PASSWORD_RESET OTP and mark it as verified (without consuming).

        Returns (success, otp). Sets is_verified=True so the reset-password
        step can confirm the OTP was previously validated.
        """
        otp = cls._match_otp(identifier, code, purpose="PASSWORD_RESET")

        if otp is None:
            return False, None

        otp.is_verified = True
        otp.save(update_fields=["is_verified"])
        return True, otp
