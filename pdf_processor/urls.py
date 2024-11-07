from django.urls import path
from .views import PDFExtractAPI, upload_pdf

urlpatterns = [
    path('', upload_pdf, name='upload_pdf'),
    path('api/extract/', PDFExtractAPI.as_view(), name='pdf_extract_api'),
] 