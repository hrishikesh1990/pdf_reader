from rest_framework import serializers

class PDFUrlSerializer(serializers.Serializer):
    url = serializers.URLField(required=True)

class PDFExtractResponseSerializer(serializers.Serializer):
    text = serializers.CharField()
    links = serializers.DictField() 