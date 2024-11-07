from .base import *

DEBUG = True
SECRET_KEY = 'django-insecure-your-dev-key'  # Only for development

ALLOWED_HOSTS = ['localhost', '127.0.0.1']

# Remove whitenoise for development
if 'whitenoise.middleware.WhiteNoiseMiddleware' in MIDDLEWARE:
    MIDDLEWARE.remove('whitenoise.middleware.WhiteNoiseMiddleware')

# Use simple storage for development
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
} 