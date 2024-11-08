from django import forms

class PDFUploadForm(forms.Form):
    pdf_file = forms.FileField(
        label='Upload PDF',
        help_text='Upload a PDF file for processing'
    )
    processing_type = forms.ChoiceField(
        choices=[
            ('direct', 'Parse PDF directly'),
            ('ocr', 'Convert to image and run OCR')
        ],
        widget=forms.RadioSelect,
        initial='direct'
    ) 