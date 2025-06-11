# pdfparser/views.py
import json
import logging
# import re # No longer needed for markdown stripping here, as analyze_brd handles it
from django.shortcuts import render
from django.http import JsonResponse
from .utils.brd_parser import extract_text_from_pdf
from core.services.gemini_client import analyze_brd # Ensure this import path is correct

# You'll need these for docx/doc parsing if you decide to implement them
# from docx import Document # pip install python-docx
# from textract import process # pip install textract (might have external dependencies)

logger = logging.getLogger(__name__)

def upload_brd_view(request):
    if request.method == 'POST':
        uploaded_file = request.FILES.get('brd_file')
        
        response_data = {
            'status': 'error',
            'message': 'An unknown error occurred.',
            'analysis_data': None,
            'extracted_text': None,
            'raw_ai_response': None # For debugging the raw AI response if it's an error
        }
    
        if not uploaded_file:
            response_data['message'] = "No file was uploaded. Please select a file and try again."
            logger.warning("AJAX: No file uploaded in POST request.")
            return JsonResponse(response_data, status=400)
    
        filename = uploaded_file.name
    
        try:
            file_extension = uploaded_file.name.lower().split('.')[-1]
            extracted_text = None
    
            if file_extension == 'pdf':
                extracted_text = extract_text_from_pdf(uploaded_file)
            elif file_extension == 'txt':
                extracted_text = uploaded_file.read().decode('utf-8')
            # Add DOCX/DOC parsing here once implemented in brd_parser.py
            # elif file_extension == 'docx':
            #     extracted_text = extract_text_from_docx(uploaded_file)
            # elif file_extension == 'doc':
            #     response_data['message'] = "'.doc' files require additional setup (e.g., textract) on the server. Please upload .pdf, .docx, or .txt."
            #     return JsonResponse(response_data, status=400)
            else:
                response_data['message'] = f"Unsupported file type: '.{file_extension}'. Please upload PDF, DOCX, or TXT."
                logger.warning(f"AJAX: Unsupported file upload attempt: {uploaded_file.name}")
                return JsonResponse(response_data, status=400)
    
            if not extracted_text:
                response_data['message'] = "Could not extract text from the uploaded file. It might be empty, corrupted, or an unsupported format despite the extension."
                return JsonResponse(response_data, status=400)
    
            logger.info(f"AJAX: Successfully extracted text from {uploaded_file.name}")
            
            # --- AI Model Call and Response Processing ---
            # analyze_brd now returns either the parsed JSON (dict) or an error dict/string
            ai_result = analyze_brd(extracted_text)
            
            # Check if the AI analysis result is an error (e.g., JSON parsing failed inside gemini_client)
            if isinstance(ai_result, dict) and (ai_result.get('error') or ai_result.get('JSON_PARSE_ERROR')):
                response_data['status'] = 'error'
                response_data['message'] = ai_result.get('details', 'AI analysis failed to produce valid JSON structure.')
                response_data['analysis_data'] = None # No valid data if error
                response_data['extracted_text'] = extracted_text
                response_data['raw_ai_response'] = ai_result.get('raw_ai_response', 'N/A') # Pass raw AI response for debugging
                logger.error(f"AI analysis failed for {filename}: {response_data['message']}. Raw AI: {response_data['raw_ai_response']}")
                return JsonResponse(response_data, status=500)
            elif isinstance(ai_result, str): # Catch general string errors from analyze_brd (less likely with new gemini_client)
                response_data['status'] = 'error'
                response_data['message'] = f"AI analysis failed: {ai_result}"
                response_data['analysis_data'] = None
                response_data['extracted_text'] = extracted_text
                response_data['raw_ai_response'] = ai_result
                logger.error(f"AI analysis failed for {filename}: {response_data['message']}")
                return JsonResponse(response_data, status=500)
            else:
                # If no error, ai_result is the valid parsed JSON dictionary
                response_data['status'] = 'success'
                response_data['message'] = 'BRD analyzed successfully.'
                response_data['analysis_data'] = ai_result
                response_data['extracted_text'] = extracted_text # Send extracted text back for display/debugging
                # For `raw_ai_response`, convert the dictionary back to a string for display if needed
                response_data['raw_ai_response'] = json.dumps(ai_result, indent=2) 
                logger.info("AJAX: AI response parsed as JSON successfully.")
                return JsonResponse(response_data)
                
        except Exception as e:
            logger.exception(f"AJAX: An unexpected server-side error occurred during file processing or AI analysis for {filename}.")
            response_data['message'] = f"An internal server error occurred: {e}"
            return JsonResponse(response_data, status=500)
            
    # For GET requests, render the initial HTML page
    return render(request, 'brd-upload.html')