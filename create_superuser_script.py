import os
import django

# Setup Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from django.contrib.auth import get_user_model

def create_superuser():
    User = get_user_model()
    username = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'admin')
    email = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@example.com')
    password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')

    if not password:
        print("No DJANGO_SUPERUSER_PASSWORD set. Skipping superuser creation.")
        return

    if User.objects.filter(username=username).exists():
        print(f"Superuser '{username}' already exists. Skipping.")
    else:
        print(f"Creating superuser '{username}'...")
        User.objects.create_superuser(username=username, email=email, password=password)
        print("Superuser created successfully!")

if __name__ == "__main__":
    create_superuser()
