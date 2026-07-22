import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apps.accounts.models import User, Role

def recreate_super_admin():
    """Create or reactivate the main super admin account."""
    username = "jayvadi"
    email = "jayvadi@example.com"
    default_password = "Admin@123"

    if User.objects.filter(username=username).exists():
        print(f"User '{username}' already exists!")
        user = User.objects.get(username=username)
        user.is_active = True
        user.role = Role.SUPER_ADMIN
        user.is_superuser = True
        user.is_staff = True
        user.save()
        print(f"User reactivated and set to SUPER_ADMIN (main admin).")
        return

    # Create new super admin user
    user = User.objects.create_superuser(
        username=username,
        email=email,
        password=default_password,
    )
    user.role = Role.SUPER_ADMIN
    user.is_active = True
    user.save()
    # Demote any other is_superuser users
    User.objects.exclude(pk=user.pk).filter(is_superuser=True).update(is_superuser=False)
    print(f"Successfully recreated '{username}' admin user!")
    print(f"Username: {username}")
    print(f"Password: {default_password}")
    print("Please change the password after logging in!")

if __name__ == "__main__":
    recreate_super_admin()
