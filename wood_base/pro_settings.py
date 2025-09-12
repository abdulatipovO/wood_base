from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent


ALLOWED_HOSTS = ['*']

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'woodapp_db',        # DB nomi
        'USER': 'woodapp_user',      # foydalanuvchi
        'PASSWORD': 'WoodApp0233',  # parol
        'HOST': 'localhost',           # yoki server IP
        'PORT': '5432',                # default postgres port
    }
}

__all__ = ['ALLOWED_HOSTS',"DATABASES"]