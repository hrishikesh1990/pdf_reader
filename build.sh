#!/usr/bin/env bash
# exit on error
set -o errexit

# Add Tesseract repository for latest version
add-apt-repository -y ppa:alex-p/tesseract-ocr5

# Update package list
apt-get update

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

# Set Tesseract path in environment
echo "export TESSDATA_PREFIX=/usr/share/tesseract-ocr/4.00/tessdata/" >> ~/.bashrc
export TESSDATA_PREFIX=/usr/share/tesseract-ocr/4.00/tessdata/

# Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Collect static files
python manage.py collectstatic --no-input

# Run migrations
python manage.py migrate