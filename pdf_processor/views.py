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

def upload_pdf(request):
    if request.method == 'POST':
        form = PDFUploadForm(request.POST, request.FILES)
        if form.is_valid():
            pdf_file = request.FILES['pdf_file']
            
            if not pdf_file.name.endswith('.pdf'):
                return render(request, 'pdf_processor/upload.html', {
                    'form': form,
                    'error': 'Please upload a PDF file'
                })
            
            try:
                # Extract text using all methods
                text_results = PDFTextExtractor.extract_text_all_methods(pdf_file)
                
                # Reset file pointer for link extraction
                pdf_file.seek(0)
                
                # Extract links
                links = LinkExtractor.extract_all_links(pdf_file, '\n'.join(text_results.values()))
                
                return render(request, 'pdf_processor/results.html', {
                    'text_results': text_results,
                    'links': links
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
