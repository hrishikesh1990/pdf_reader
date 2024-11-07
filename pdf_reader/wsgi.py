"""
WSGI config for pdf_reader project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/howto/deployment/wsgi/
"""

import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pdf_reader.settings')
os.environ.setdefault('DJANGO_ENV', 'production')  # Set to production for Render

application = get_wsgi_application()
