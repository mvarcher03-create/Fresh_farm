from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.apps import apps
import os

class Command(BaseCommand):
    help = 'Creates or updates the admin user'

    def handle(self, *args, **options):
        # Ensure all apps are loaded
        apps.get_models()
        
        User = get_user_model()
        username = os.getenv('DJANGO_SUPERUSER_USERNAME', 'admin')
        password = os.getenv('DJANGO_SUPERUSER_PASSWORD', 'admin123password')
        email = os.getenv('DJANGO_SUPERUSER_EMAIL', 'admin@example.com')
        
        try:
            if not User.objects.filter(username=username).exists():
                User.objects.create_superuser(username=username, email=email, password=password)
                self.stdout.write(self.style.SUCCESS(f'Successfully created superuser: {username}'))
            else:
                user = User.objects.get(username=username)
                user.set_password(password)
                user.email = email
                user.is_staff = True
                user.is_superuser = True
                user.save()
                self.stdout.write(self.style.SUCCESS(f'Successfully updated superuser: {username}'))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Error creating/updating admin user: {str(e)}'))
