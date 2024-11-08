from rest_framework import serializers

class PDFUrlSerializer(serializers.Serializer):
    pdf_url = serializers.URLField(help_text="URL of the PDF file to process")

class PDFExtractResponseSerializer(serializers.Serializer):
    direct_text = serializers.DictField(help_text="Text extracted directly from PDF using various methods")
    ocr_text = serializers.DictField(help_text="Text extracted using OCR")
    links = serializers.DictField(help_text="Links extracted from the PDF")
    error = serializers.CharField(required=False, help_text="Error message if processing failed") 