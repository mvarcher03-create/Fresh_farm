"""
WSGI config for fresh_project project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import os
import sys
from pathlib import Path

# Add the project directory to the Python path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fresh_project.settings')

# Create/update admin user on startup
try:
    from django.contrib.auth import get_user_model
    from django.db.utils import OperationalError
    
    print("Attempting to create/update admin user...")
    User = get_user_model()
    username = os.getenv('DJANGO_SUPERUSER_USERNAME', 'admin')
    password = os.getenv('DJANGO_SUPERUSER_PASSWORD', 'admin123password')
    email = os.getenv('DJANGO_SUPERUSER_EMAIL', 'admin@example.com')
    
    try:
        if not User.objects.filter(username=username).exists():
            User.objects.create_superuser(username=username, email=email, password=password)
            print(f"Superuser {username} created successfully!")
        else:
            user = User.objects.get(username=username)
            user.set_password(password)
            user.email = email
            user.is_staff = True
            user.is_superuser = True
            user.save()
            print(f"Superuser {username} updated successfully!")
    except OperationalError:
        print("Database not ready or accessible. Admin user will be created when database is available.")
except Exception as e:
    print(f"Error creating/updating admin user: {str(e)}")

application = get_wsgi_application()
