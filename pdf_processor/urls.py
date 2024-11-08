from django.urls import path
from .views import upload_pdf, PDFProcessAPIView

urlpatterns = [
    path('', upload_pdf, name='upload_pdf'),
    path('api/process/', PDFProcessAPIView.as_view(), name='process_pdf_api'),
] 