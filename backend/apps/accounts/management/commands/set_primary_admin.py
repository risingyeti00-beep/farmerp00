"""
Make a specific user the sole main super admin (is_superuser=True).

Usage:
    python manage.py set_primary_admin --username=jayvadi

What it does:
    1. Finds the user with the given username (default: jayvadi)
    2. Sets that user as the primary admin (is_superuser=True, is_staff=True, role=SUPER_ADMIN, is_active=True)
    3. Sets ALL other users' is_superuser=False so only the specified user has Django superuser status

Run this BEFORE the reset_super_admin endpoint or update_super_admin command to ensure
the correct account owns the main super admin flag.
"""
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = "Make a specific user the sole main super admin (is_superuser=True)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--username",
            type=str,
            default="jayvadi",
            help="Username to promote to main super admin (default: jayvadi)",
        )

    def handle(self, *args, **options):
        target_username = options["username"]

        # Step 1: Find the target user (including soft-deleted, so we can restore them)
        target = User.objects.filter(username=target_username).first()
        if not target:
            self.stderr.write(
                self.style.ERROR(
                    f"User '{target_username}' not found in the database. "
                    "Available super admin users:"
                )
            )
            admins = User.objects.filter(role="SUPER_ADMIN").values(
                "username", "email", "is_superuser", "is_active"
            )
            for a in admins:
                self.stdout.write(f"  • {a['username']}  (email={a['email']}, is_superuser={a['is_superuser']}, active={a['is_active']})")
            return

        # Step 2: Promote the target user to main super admin
        old_is_superuser = target.is_superuser
        target.is_superuser = True
        target.is_staff = True
        target.role = "SUPER_ADMIN"
        target.is_active = True
        target.save(update_fields=["is_superuser", "is_staff", "role", "is_active"])

        if not old_is_superuser:
            self.stdout.write(
                self.style.SUCCESS(f"✅ Promoted '{target_username}' to main super admin (is_superuser=True)")
            )
        else:
            self.stdout.write(f"  '{target_username}' was already the main super admin")

        # Step 3: Demote ALL other users — remove is_superuser from everyone else
        demoted_count = User.objects.exclude(pk=target.pk).filter(is_superuser=True).update(is_superuser=False)

        if demoted_count > 0:
            self.stdout.write(
                self.style.WARNING(f"⚠️  Removed is_superuser from {demoted_count} other user(s)")
            )
        else:
            self.stdout.write("  No other users had is_superuser=True")

        # Step 4: Summary
        self.stdout.write(f"\n{'─' * 50}")
        self.stdout.write(f"Primary admin:   {target.username}  (email={target.email})")
        self.stdout.write(f"Role:            {target.role}")
        self.stdout.write(f"is_superuser:    {target.is_superuser}")
        self.stdout.write(f"is_staff:        {target.is_staff}")
        self.stdout.write(f"Total super admins in DB: {User.objects.filter(role='SUPER_ADMIN').count()}")
        self.stdout.write(f"Users with is_superuser:  {User.objects.filter(is_superuser=True).count()} (should be 1)")
        self.stdout.write(f"{'─' * 50}")

        if demoted_count > 0:
            self.stdout.write(
                self.style.WARNING(
                    "\n⚠️  Previous main admin 'risingyeti' has been demoted.\n"
                    "   Update the reset_super_admin endpoint and update_super_admin command\n"
                    "   to use 'jayvadi' instead of 'risingyeti' so emergency resets work."
                )
            )
