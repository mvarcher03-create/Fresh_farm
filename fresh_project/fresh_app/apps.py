from django.apps import AppConfig
from django.contrib.auth import get_user_model
from django.db.utils import OperationalError, ProgrammingError
import os

class FreshAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'fresh_app'

    def ready(self):
        """Ensure a superuser exists based on DJANGO_SUPERUSER_* env vars.

        This runs at startup (including on Render) and will create or update
        the superuser with the username/email/password defined in the
        environment variables if they are set.
        """
        username = os.environ.get("DJANGO_SUPERUSER_USERNAME")
        email = os.environ.get("DJANGO_SUPERUSER_EMAIL")
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD")

        # Only proceed if we have at least username and password
        if not username or not password:
            return

        try:
            User = get_user_model()
            user, created = User.objects.get_or_create(
                username=username,
                defaults={"email": email or ""},
            )

            # Make sure it's a usable, active superuser
            user.is_superuser = True
            user.is_staff = True
            if email:
                user.email = email
            user.is_active = True
            user.set_password(password)
            user.save()
        except (OperationalError, ProgrammingError):
            # Database not ready (e.g. before migrations) – safely ignore.
            pass
