from .base import *

DEBUG = False
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY')

ALLOWED_HOSTS = [
    'pdf-reader-vsf5.onrender.com',
    'localhost',
    '127.0.0.1',
    '*',
]

# Add whitenoise middleware
if 'whitenoise.middleware.WhiteNoiseMiddleware' not in MIDDLEWARE:
    MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')

# Whitenoise configuration
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Security settings
CSRF_TRUSTED_ORIGINS = [
    'https://pdf-reader-vsf5.onrender.com',
]

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Database (use environment variables for production)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
} 