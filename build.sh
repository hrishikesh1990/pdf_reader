#!/usr/bin/env bash
# exit on error
set -o errexit

# Set environment variables
export DJANGO_ENV=production

# Create directories if they don't exist
mkdir -p staticfiles
mkdir -p static

# Ensure static directory has proper permissions
chmod -R 755 static
chmod -R 755 staticfiles

pip install -r requirements.txt

python manage.py collectstatic --no-input
python manage.py migrate