from django.shortcuts import render
from .forms import PDFUploadForm
import PyPDF2
import pdfplumber
import io
from pdf2image import convert_from_bytes
import pytesseract
from pdfminer.high_level import extract_text as pdfminer_extract
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.converter import TextConverter
from pdfminer.layout import LAParams
from pdfminer.pdfpage import PDFPage
import re
import fitz  # PyMuPDF
from urllib.parse import urlparse
import logging
from io import BytesIO
import requests
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import PDFUrlSerializer, PDFExtractResponseSerializer
from django.core.files.uploadedfile import InMemoryUploadedFile
import os
from PIL import Image
import tempfile
from pdf2image import convert_from_path

# Try to import swagger_auto_schema, but don't fail if it's not available
try:
    from drf_yasg.utils import swagger_auto_schema
    SWAGGER_AVAILABLE = True
except ImportError:
    SWAGGER_AVAILABLE = False
    # Create a dummy decorator that does nothing
    def swagger_auto_schema(*args, **kwargs):
        def decorator(f):
            return f
        return decorator

def extract_links(text):
    # Regular expressions for different types of links
    patterns = {
        'web_links': r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+[^\s]*',
        'linkedin': r'https?://(?:www\.)?linkedin\.com/\S+',
        'github': r'https?://(?:www\.)?github\.com/\S+',
        'stackoverflow': r'https?://(?:www\.)?stackoverflow\.com/\S+'
    }
    
    links = {}
    for link_type, pattern in patterns.items():
        links[link_type] = list(set(re.findall(pattern, text, re.IGNORECASE)))
    
    return links

class PDFTextExtractor:
    @staticmethod
    def extract_with_pypdf2(pdf_file):
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
        return text.strip()
    
    @staticmethod
    def extract_with_pdfplumber(pdf_file):
        text = ""
        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                text += page.extract_text() or "" + "\n"
        return text.strip()
    
    @staticmethod
    def extract_with_ocr(pdf_file):
        try:
            # Convert PDF to images
            images = convert_from_bytes(pdf_file.read())
            text = ""
            for image in images:
                # Extract text from each image
                text += pytesseract.image_to_string(image) + "\n"
            return text.strip()
        except Exception as e:
            print(f"OCR Error: {str(e)}")
            return ""
    
    @staticmethod
    def extract_with_pdfminer(pdf_file):
        try:
            text = pdfminer_extract(pdf_file)
            return text.strip()
        except Exception as e:
            print(f"PDFMiner Error: {str(e)}")
            return ""
    
    @staticmethod
    def extract_with_pymupdf(pdf_file):
        try:
            # Convert the file to bytes for PyMuPDF
            pdf_bytes = pdf_file.read()
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            
            text = ""
            for page in doc:
                text += page.get_text() + "\n"
                
            doc.close()
            return text.strip()
        except Exception as e:
            print(f"PyMuPDF Error: {str(e)}")
            return ""
    
    @classmethod
    def extract_text_all_methods(cls, pdf_file):
        # Create a copy of the file content for each method
        pdf_content = pdf_file.read()
        pdf_file.seek(0)  # Reset file pointer
        
        results = {
            'PyMuPDF': '',
            'PyPDF2': '',
            'pdfplumber': '',
            'OCR': '',
            'pdfminer': ''
        }
        
        # Try PyMuPDF
        try:
            results['PyMuPDF'] = cls.extract_with_pymupdf(pdf_file)
        except Exception as e:
            print(f"PyMuPDF Error: {str(e)}")
        
        # Try each method and store results
        try:
            results['PyPDF2'] = cls.extract_with_pypdf2(pdf_file)
        except Exception as e:
            print(f"PyPDF2 Error: {str(e)}")
        
        pdf_file.seek(0)  # Reset file pointer
        try:
            results['pdfplumber'] = cls.extract_with_pdfplumber(pdf_file)
        except Exception as e:
            print(f"pdfplumber Error: {str(e)}")
        
        pdf_file.seek(0)  # Reset file pointer
        results['OCR'] = cls.extract_with_ocr(pdf_file)
        
        pdf_file.seek(0)  # Reset file pointer
        results['pdfminer'] = cls.extract_with_pdfminer(pdf_file)
        
        return results

class LinkExtractor:
    @staticmethod
    def is_valid_url(url):
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except:
            return False

    @staticmethod
    def clean_url(url):
        # Remove trailing punctuation, whitespace, and quotes
        url = url.strip(' "\'')
        url = re.sub(r'[.,;:]$', '', url)
        
        # Add https:// to www. urls or domain-only urls
        if url.startswith('www.'):
            url = f'https://{url}'
        elif re.match(r'^(linkedin\.com|github\.com)', url):
            url = f'https://www.{url}'
        
        return url

    @staticmethod
    def extract_links_from_text(text, page_num=1):
        """Extract links from text"""
        if not text:
            return []

        all_links = []
        
        # Regular expression patterns
        patterns = {
            'url': r'(?:https?://|www\.)[^\s<>"\{\}\|\\\^\[\]`\s]+',
            'email': r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
            'linkedin': [
                r'(?:https?://)?(?:[\w]+\.)?linkedin\.com/in/[a-zA-Z0-9\-_%]+(?:/[^\s<>\[\]]+)?',
                r'(?:https?://)?(?:[\w]+\.)?linkedin\.com/company/[a-zA-Z0-9\-_%]+(?:/[^\s<>\[\]]+)?',
                r'linkedin\.com/(?:in/|company/|mwlite/|pub/)?[\w\-_%]+',
            ],
            'github': [
                r'(?:https?://)?(?:[\w]+\.)?github\.com/[a-zA-Z0-9\-_%]+/[a-zA-Z0-9\-_.]+',
                r'(?:https?://)?(?:[\w]+\.)?github\.com/[a-zA-Z0-9\-_%]+',
                r'github\.com/[^\s<>\[\]]+',
            ]
        }

        # Extract LinkedIn URLs
        for pattern in patterns['linkedin']:
            matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                url = match.group()
                if not url.startswith(('http://', 'https://')):
                    url = f"https://www.{url}"
                all_links.append({
                    'page': page_num,
                    'type': 'linkedin',
                    'uri': url
                })

        # Extract GitHub URLs
        for pattern in patterns['github']:
            matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                url = match.group()
                if not url.startswith(('http://', 'https://')):
                    url = f"https://www.{url}"
                all_links.append({
                    'page': page_num,
                    'type': 'github',
                    'uri': url
                })

        # Extract general URLs
        matches = re.finditer(patterns['url'], text, re.IGNORECASE)
        for match in matches:
            url = LinkExtractor.clean_and_validate_url(match.group())
            if url:
                link_type = 'text'
                if 'stackoverflow.com' in url.lower():
                    link_type = 'stackoverflow'
                elif 'linkedin.com' in url.lower():
                    link_type = 'linkedin'
                elif 'github.com' in url.lower():
                    link_type = 'github'
                
                all_links.append({
                    'page': page_num,
                    'type': link_type,
                    'uri': url
                })

        return all_links

    @staticmethod
    def extract_annotation_links(pdf_file):
        """Extract clickable links from PDF annotations"""
        try:
            reader = PyPDF2.PdfReader(pdf_file)
            annotation_links = []

            for page_num, page in enumerate(reader.pages, 1):
                if '/Annots' in page:
                    annotations = page['/Annots']
                    if annotations:
                        for annotation in annotations:
                            if annotation.get('/Subtype') == '/Link' and '/A' in annotation:
                                action = annotation['/A']
                                if '/URI' in action:
                                    uri = action['/URI']
                                    annotation_links.append({
                                        'page': page_num,
                                        'type': 'annotation',
                                        'uri': uri
                                    })

            return annotation_links
        except Exception as e:
            logging.error(f"Error extracting annotation links: {str(e)}")
            return []

    @staticmethod
    def extract_annotations_with_pymupdf(pdf_file):
        """Extract clickable links using PyMuPDF"""
        try:
            # Convert Django's UploadedFile to bytes
            pdf_bytes = pdf_file.read()
            pdf_file.seek(0)  # Reset file pointer
            
            # Create a BytesIO object
            pdf_stream = BytesIO(pdf_bytes)
            
            doc = fitz.open(stream=pdf_stream, filetype="pdf")
            annotation_links = []
            
            for page_num, page in enumerate(doc, 1):
                # Get all links from the page
                links = page.get_links()
                
                for link in links:
                    if link.get('uri'):
                        uri = link['uri']
                        # Get the rect coordinates
                        rect = link.get('from')
                        
                        if rect:
                            # Get text in and around the link area
                            try:
                                # Create a proper fitz.Rect object
                                rect = fitz.Rect(rect)
                                # Expand rectangle slightly
                                expanded_rect = rect + (-2, -2, 2, 2)
                                text_around = page.get_text("text", clip=expanded_rect)
                            except Exception as e:
                                logging.error(f"Error getting text around link: {str(e)}")
                                text_around = ""
                            
                            link_data = {
                                'page': page_num,
                                'uri': uri,
                                'text': text_around.strip(),
                                'type': 'annotation'
                            }
                            annotation_links.append(link_data)
                            logging.debug(f"Found annotation link: {uri} with text: {text_around.strip()}")
            
            doc.close()
            return annotation_links
            
        except Exception as e:
            logging.error(f"Error extracting PyMuPDF annotations: {str(e)}")
            return []

    @staticmethod
    def categorize_link(url, anchor_text=''):
        """Categorize a link based on URL and anchor text"""
        url_lower = url.lower()
        anchor_lower = anchor_text.lower() if anchor_text else ''
        
        # GitHub detection
        if ('github.com' in url_lower or 
            'github' in anchor_lower or 
            bool(re.search(r'github\.com/[\w-]+(?:/[\w-]+)?', url_lower))):
            return 'github'
            
        # LinkedIn detection
        if ('linkedin.com' in url_lower or 
            'linkedin' in anchor_lower or 
            bool(re.search(r'linkedin\.com/(?:in|company)/[\w-]+', url_lower))):
            return 'linkedin'
            
        # StackOverflow detection
        if 'stackoverflow.com' in url_lower:
            return 'stackoverflow'
            
        return 'text'

    @staticmethod
    def clean_and_validate_url(url, anchor_text=''):
        """Clean and validate URL"""
        url = url.strip(' "\'')
        url = re.sub(r'[.,;:]$', '', url)
        
        if not url.startswith(('http://', 'https://')):
            if url.startswith('www.'):
                url = f"https://{url}"
            else:
                url = f"https://www.{url}"
        
        return url

    @staticmethod
    def extract_all_links(pdf_file, extracted_text):
        """Extract both annotation and text-based links"""
        all_links = []
        
        # Get annotation links
        annotation_links = LinkExtractor.extract_annotations_with_pymupdf(pdf_file)
        all_links.extend(annotation_links)
        
        # Get text-based links
        text_links = LinkExtractor.extract_links_from_text(extracted_text)
        all_links.extend(text_links)

        # Remove duplicates while preserving order
        seen = set()
        unique_links = []
        for link in all_links:
            uri = link['uri']
            if uri not in seen:
                seen.add(uri)
                unique_links.append(link)

        # Group links by type
        grouped_links = {
            'web_links': [],
            'linkedin': [],
            'github': [],
            'stackoverflow': [],
            'email': [],
            'annotation': []
        }

        for link in unique_links:
            link_type = link['type']
            if link_type in grouped_links:
                grouped_links[link_type].append(link['uri'])
            else:
                grouped_links['web_links'].append(link['uri'])

        return grouped_links

def is_image_file(file):
    """Check if the file is an image based on its content"""
    try:
        Image.open(file)
        file.seek(0)  # Reset file pointer
        return True
    except Exception:
        file.seek(0)  # Reset file pointer
        return False

def is_pdf_file(file):
    """Check if the file is a PDF based on its name or content"""
    return file.name.lower().endswith('.pdf')

def extract_text_from_image(image_file):
    """Extract text from image using OCR"""
    try:
        # Open the image using PIL
        image = Image.open(image_file)
        
        # Extract text using pytesseract
        text = pytesseract.image_to_string(image)
        
        return {'OCR': text}
    except Exception as e:
        logging.error(f"OCR Error: {str(e)}")
        return {'OCR': f"Error processing image: {str(e)}"}

def process_pdf_with_ocr(pdf_file):
    """Convert PDF to images and run OCR"""
    try:
        # Create a temporary file to save the uploaded PDF
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_pdf:
            tmp_pdf.write(pdf_file.read())
            pdf_path = tmp_pdf.name

        # Convert PDF to images
        images = convert_from_path(pdf_path)
        
        # Process each page with OCR
        text_results = []
        for i, image in enumerate(images):
            text = pytesseract.image_to_string(image)
            text_results.append(f"Page {i+1}:\n{text}\n")

        # Clean up temporary file
        os.unlink(pdf_path)
        
        return {'OCR': '\n'.join(text_results)}
    except Exception as e:
        logging.error(f"OCR Error: {str(e)}")
        return {'OCR': f"Error processing PDF with OCR: {str(e)}"}

def upload_pdf(request):
    if request.method == 'POST':
        form = PDFUploadForm(request.POST, request.FILES)
        if form.is_valid():
            pdf_file = request.FILES['pdf_file']
            processing_type = form.cleaned_data['processing_type']
            
            if not pdf_file.name.lower().endswith('.pdf'):
                return render(request, 'pdf_processor/upload.html', {
                    'form': form,
                    'error': 'Please upload a PDF file'
                })
            
            try:
                if processing_type == 'direct':
                    # Process PDF directly
                    text_results = PDFTextExtractor.extract_text_all_methods(pdf_file)
                    pdf_file.seek(0)
                    links = LinkExtractor.extract_all_links(pdf_file, '\n'.join(text_results.values()))
                else:  # processing_type == 'ocr'
                    # Process PDF with OCR
                    text_results = process_pdf_with_ocr(pdf_file)
                    links = {}  # No link extraction for OCR processing
                
                return render(request, 'pdf_processor/results.html', {
                    'text_results': text_results,
                    'links': links,
                    'processing_type': processing_type
                })
            except Exception as e:
                logging.error(f"Error processing PDF: {str(e)}")
                return render(request, 'pdf_processor/upload.html', {
                    'form': form,
                    'error': f'Error processing PDF: {str(e)}'
                })
    else:
        form = PDFUploadForm()
    
    return render(request, 'pdf_processor/upload.html', {'form': form})

class PDFExtractAPI(APIView):
    def post(self, request):
        # Validate input
        serializer = PDFUrlSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        pdf_url = serializer.validated_data['url']
        
        try:
            # Download PDF
            response = requests.get(pdf_url, timeout=30)
            response.raise_for_status()  # Raise exception for bad status codes
            
            # Check if it's actually a PDF
            content_type = response.headers.get('content-type', '')
            if 'application/pdf' not in content_type.lower():
                return Response(
                    {'error': 'The URL does not point to a PDF file'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Create BytesIO object from the downloaded content
            pdf_content = BytesIO(response.content)
            
            # Extract text using PyMuPDF
            extracted_text = ""
            try:
                doc = fitz.open(stream=pdf_content, filetype="pdf")
                for page in doc:
                    extracted_text += page.get_text() + "\n"
                doc.close()
            except Exception as e:
                return Response(
                    {'error': f'Error extracting text from PDF: {str(e)}'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            # Create a Django file object for link extraction
            pdf_content.seek(0)
            pdf_file = InMemoryUploadedFile(
                pdf_content,
                'pdf_file',
                'temp.pdf',
                'application/pdf',
                len(response.content),
                None
            )
            
            # Extract links
            try:
                links = LinkExtractor.extract_all_links(pdf_file, extracted_text)
            except Exception as e:
                return Response(
                    {'error': f'Error extracting links from PDF: {str(e)}'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            # Prepare response
            result = {
                'text': extracted_text,
                'links': links
            }
            
            # Validate output
            response_serializer = PDFExtractResponseSerializer(data=result)
            if response_serializer.is_valid():
                return Response(response_serializer.validated_data, status=status.HTTP_200_OK)
            else:
                return Response(
                    response_serializer.errors,
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
        except requests.RequestException as e:
            return Response(
                {'error': f'Error downloading PDF: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {'error': f'Unexpected error: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class PDFProcessAPIView(APIView):
    """API endpoint for processing PDFs"""
    
    def post(self, request, *args, **kwargs):
        """
        Process a PDF file and extract text using multiple methods
        """
        serializer = PDFUrlSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        pdf_url = serializer.validated_data['pdf_url']

        try:
            # Download the PDF
            response = requests.get(pdf_url)
            if response.status_code != 200:
                return Response({
                    'error': f'Failed to download PDF. Status code: {response.status_code}'
                }, status=status.HTTP_400_BAD_REQUEST)

            pdf_content = BytesIO(response.content)

            # Process PDF directly
            direct_text = self.process_pdf_directly(pdf_content)
            
            # Reset file pointer for link extraction
            pdf_content.seek(0)
            links = self.extract_links(pdf_content, '\n'.join(str(v) for v in direct_text.values()))
            
            # Reset file pointer for OCR processing
            pdf_content.seek(0)
            ocr_text = self.process_pdf_with_ocr(pdf_content)

            result = {
                'direct_text': direct_text,
                'ocr_text': ocr_text,
                'links': links
            }

            return Response(result, status=status.HTTP_200_OK)

        except Exception as e:
            logging.error(f"Error processing PDF: {str(e)}")
            return Response({
                'error': f'Error processing PDF: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def process_pdf_directly(self, pdf_content):
        """Process PDF using direct text extraction methods"""
        try:
            return PDFTextExtractor.extract_text_all_methods(pdf_content)
        except Exception as e:
            logging.error(f"Direct processing error: {str(e)}")
            return {'error': str(e)}

    def process_pdf_with_ocr(self, pdf_content):
        """Process PDF using OCR"""
        try:
            # Create temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_pdf:
                tmp_pdf.write(pdf_content.read())
                pdf_path = tmp_pdf.name

            # Convert PDF to images
            images = convert_from_path(pdf_path)
            
            # Process each page with OCR
            text_results = []
            for i, image in enumerate(images):
                text = pytesseract.image_to_string(image)
                text_results.append(f"Page {i+1}:\n{text}\n")

            # Clean up
            os.unlink(pdf_path)
            
            return {'OCR': '\n'.join(text_results)}
        except Exception as e:
            logging.error(f"OCR processing error: {str(e)}")
            return {'error': str(e)}

    def extract_links(self, pdf_content, text_content):
        """Extract links from PDF"""
        try:
            return LinkExtractor.extract_all_links(pdf_content, text_content)
        except Exception as e:
            logging.error(f"Link extraction error: {str(e)}")
            return {'error': str(e)}
