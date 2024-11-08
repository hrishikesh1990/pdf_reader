class PDFTextExtractor:
    @staticmethod
    def extract_text_all_methods(pdf_file):
        results = {}
        
        # Ensure we have a BytesIO object
        if hasattr(pdf_file, 'read'):
            if hasattr(pdf_file, 'seek'):
                pdf_file.seek(0)
            pdf_content = BytesIO(pdf_file.read())
        else:
            pdf_content = BytesIO(pdf_file)

        # PyMuPDF
        try:
            pdf_content.seek(0)
            text = PDFTextExtractor.extract_text_pymupdf(pdf_content)
            results['PyMuPDF'] = text
        except Exception as e:
            logging.error(f"PyMuPDF Error: {str(e)}")
            results['PyMuPDF'] = f"Error: {str(e)}"

        # PDFMiner
        try:
            pdf_content.seek(0)
            text = PDFTextExtractor.extract_text_pdfminer(pdf_content)
            results['PDFMiner'] = text
        except Exception as e:
            logging.error(f"PDFMiner Error: {str(e)}")
            results['PDFMiner'] = f"Error: {str(e)}"

        # PDFPlumber
        try:
            pdf_content.seek(0)
            text = PDFTextExtractor.extract_text_pdfplumber(pdf_content)
            results['PDFPlumber'] = text
        except Exception as e:
            logging.error(f"PDFPlumber Error: {str(e)}")
            results['PDFPlumber'] = f"Error: {str(e)}"

        return results 