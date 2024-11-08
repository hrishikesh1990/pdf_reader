#!/usr/bin/env bash
# exit on error
set -o errexit

# Install Python and pip
apt-get update
apt-get install -y python3 python3-pip python3-dev

# Create symlinks for python and pip
ln -sf /usr/bin/python3 /usr/bin/python
ln -sf /usr/bin/pip3 /usr/bin/pip

# Verify Python installation
python --version
pip --version

# Install system dependencies
apt-get install -y \
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-eng \
    libtesseract-dev \
    libleptonica-dev \
    pkg-config

# Verify Tesseract installation
tesseract --version

# Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Collect static files
python manage.py collectstatic --no-input

# Run migrations
python manage.py migrate