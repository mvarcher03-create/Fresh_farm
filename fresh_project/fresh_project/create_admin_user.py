import os
import sys

def create_superuser():
    import django
    from django.contrib.auth import get_user_model
    
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fresh_project.settings')
    django.setup()
    
    User = get_user_model()
    username = os.getenv('DJANGO_SUPERUSER_USERNAME', 'admin')
    password = os.getenv('DJANGO_SUPERUSER_PASSWORD', 'admin123password')
    email = os.getenv('DJANGO_SUPERUSER_EMAIL', 'admin@example.com')
    
    if not User.objects.filter(username=username).exists():
        User.objects.create_superuser(username=username, email=email, password=password)
        print(f"Superuser {username} created successfully!")
    else:
        user = User.objects.get(username=username)
        user.set_password(password)
        user.save()
        print(f"Password updated for superuser {username}")

if __name__ == "__main__":
    create_superuser()
