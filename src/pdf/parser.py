"""PDF parsing functionality for the PDF Parser application."""

import base64
import json
import io
import pandas as pd
import streamlit as st
from anthropic import Anthropic
import fitz  # PyMuPDF
from PIL import Image
import os
import cv2
import numpy as np

from src.config.examples import CALCULATIONS_EXAMPLES, SIMPLE_EXAMPLES
from src.utils.api_utils import log_api_call

def optimize_image_for_processing(pil_image):
    """Optimize a PIL Image for better OCR processing.
    
    Args:
        pil_image: PIL Image to optimize
        
    Returns:
        PIL Image: Optimized image with content centered and excess whitespace removed,
                  preserving original DPI
    """
    # Store original DPI information
    original_dpi = pil_image.info.get('dpi')
    
    # Convert PIL to OpenCV format
    cv_image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
    
    # Convert to grayscale
    gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
    
    # Apply Gaussian blur to reduce noise
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    
    # Get binary image with more aggressive thresholding
    binary = cv2.adaptiveThreshold(
        blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 31, 10
    )
    
    # Add edge detection to catch faint content
    edges = cv2.Canny(blurred, 50, 150)
    
    # Combine binary and edges
    combined = cv2.bitwise_or(binary, edges)
    
    # Remove noise with morphological operations
    kernel = np.ones((3,3), np.uint8)
    denoised = cv2.morphologyEx(combined, cv2.MORPH_OPEN, kernel)
    denoised = cv2.morphologyEx(denoised, cv2.MORPH_CLOSE, kernel)
    
    # Dilate to connect nearby components
    dilate_kernel = np.ones((5,5), np.uint8)
    dilated = cv2.dilate(denoised, dilate_kernel, iterations=1)
    
    # Find contours of content areas
    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # Filter out very small contours (noise) - reduced threshold
    min_contour_area = cv_image.shape[0] * cv_image.shape[1] * 0.00005  # 0.005% of image area
    contours = [cnt for cnt in contours if cv2.contourArea(cnt) > min_contour_area]
    
    if not contours:
        # If no contours found, return original image
        return pil_image
    
    # Find the bounding box that contains all content
    x_min, y_min, x_max, y_max = float('inf'), float('inf'), 0, 0
    
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        x_min = min(x_min, x)
        y_min = min(y_min, y)
        x_max = max(x_max, x + w)
        y_max = max(y_max, y + h)
    
    # Add smaller padding (0.5% of image size)
    padding_x = int(cv_image.shape[1] * 0.005)
    padding_y = int(cv_image.shape[0] * 0.005)
    
    x_min = max(0, x_min - padding_x)
    y_min = max(0, y_min - padding_y)
    x_max = min(cv_image.shape[1], x_max + padding_x)
    y_max = min(cv_image.shape[0], y_max + padding_y)
    
    # Crop the image to the content area
    cropped = cv_image[y_min:y_max, x_min:x_max]
    
    # Convert back to PIL and restore original DPI
    result_image = Image.fromarray(cv2.cvtColor(cropped, cv2.COLOR_BGR2RGB))
    if original_dpi:
        result_image.info['dpi'] = original_dpi
    
    return result_image

def convert_pdf_to_image(pdf_file, dpi=200, use_png=False):
    """Convert all pages of a PDF file to images with appropriate quality for Claude vision.
    
    Args:
        pdf_file: The uploaded PDF file
        dpi: The DPI to use for rendering (default 200 - good balance of quality and size)
        use_png: Whether to use PNG format (higher quality) instead of JPEG
    
    Returns:
        list of base64 encoded image data, one per page
    """
    # Save PDF temporarily
    temp_path = os.path.join(os.getcwd(), pdf_file.name)
    with open(temp_path, "wb") as f:
        f.write(pdf_file.getvalue())
    
    try:
        # Open PDF
        pdf_document = fitz.open(temp_path)
        images_base64 = []
        
        # Convert each page
        for page in pdf_document:
            # Convert to image
            pix = page.get_pixmap(matrix=fitz.Matrix(dpi/72, dpi/72))
            
            # Convert to PIL Image
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            
            # Optimize the image
            try:
                img = optimize_image_for_processing(img)
            except Exception as e:
                st.warning(f"Image optimization failed, using original image: {str(e)}")
            
            # Save to bytes
            img_byte_arr = io.BytesIO()
            if use_png:
                img.save(img_byte_arr, format='PNG')
                media_type = 'image/png'
            else:
                img.save(img_byte_arr, format='JPEG', quality=85)
                media_type = 'image/jpeg'
            img_byte_arr = img_byte_arr.getvalue()
            
            # Encode to base64
            img_base64 = base64.b64encode(img_byte_arr).decode('utf-8')
            images_base64.append((img_base64, media_type))
            
        return images_base64
        
    finally:
        # Clean up
        if 'pdf_document' in locals():
            pdf_document.close()
        if os.path.exists(temp_path):
            os.remove(temp_path)

def process_pdf_files(uploaded_files, split_files, prompt, include_calculations, status_container=None, progress_bar=None, total_files=None, use_vision=False, use_png=False):
    """Process PDF files through the Claude API.
    
    Args:
        uploaded_files: List of uploaded PDF files
        split_files: List of tuples (file_type, file_name, file_content) for split PDFs
        prompt: The prompt to send to Claude
        include_calculations: Whether to include calculations in the output
        status_container: Streamlit container for status messages
        progress_bar: Streamlit progress bar
        total_files: Total number of files to process
        use_vision: Whether to process PDFs as images
        use_png: Whether to use PNG format for images
    
    Returns:
        DataFrame containing the extracted data
    """
    individual_results = []
    api_logs = []
    files_processed = 0

    # Create the client with custom headers
    pdf_client = Anthropic(
        api_key=st.secrets["ANTHROPIC_API_KEY"],
        default_headers={"anthropic-beta": "pdfs-2024-09-25"} if not use_vision else {}
    )

    def update_progress():
        if progress_bar and total_files:
            progress_bar.progress(files_processed / total_files)
        if status_container:
            status_container.markdown(f"Processing files ({files_processed} out of {total_files})...")

    # Process regular uploaded files
    for pdf_file in uploaded_files:
        try:
            result = process_single_pdf(pdf_client, pdf_file, prompt, include_calculations, use_vision, use_png)
            if result:
                individual_results.append(result)
            files_processed += 1
            update_progress()
        except Exception as e:
            handle_processing_error(pdf_file, e, api_logs)
            files_processed += 1
            update_progress()

    # Process split PDFs
    for file_type, file_name, file_content in split_files:
        try:
            # Create a temporary BytesIO object to simulate a file upload
            temp_file = io.BytesIO(file_content)
            temp_file.name = file_name
            
            result = process_single_pdf(pdf_client, temp_file, prompt, include_calculations, use_vision, use_png)
            if result:
                individual_results.append(result)
            files_processed += 1
            update_progress()
        except Exception as e:
            handle_processing_error(temp_file, e, api_logs)
            files_processed += 1
            update_progress()

    # Store API logs in session state
    st.session_state.api_logs = api_logs

    # Create DataFrame from results
    if individual_results:
        df = pd.DataFrame(individual_results)
        columns = ['filename'] + [col for col in df.columns if col != 'filename']
        return df[columns]
    
    return None

def process_single_pdf(client, pdf_file, prompt, include_calculations, use_vision=False, use_png=False):
    """Process a single PDF file through the Claude API.
    
    Args:
        client: The Anthropic client
        pdf_file: The PDF file to process
        prompt: The prompt to send to Claude
        include_calculations: Whether to include calculations
        use_vision: Whether to process the PDF as an image
        use_png: Whether to use PNG format for images
    
    Returns:
        dict: The extracted data
    """
    if use_vision:
        # Convert PDF to images
        images_data = convert_pdf_to_image(pdf_file, use_png=use_png)
        
        # Create message content with all images
        message_content = []
        
        # Add all images first
        for img_data, media_type in images_data:
            message_content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": img_data
                }
            })
        
        # Add examples and prompt
        message_content.extend([
            {
                "type": "text",
                "text": CALCULATIONS_EXAMPLES if include_calculations else SIMPLE_EXAMPLES
            },
            {
                "type": "text",
                "text": prompt
            }
        ])
    else:
        # Regular PDF processing - exactly as it was before
        message_content = [
            {
                "type": "document",
                "source": {
                    "type": "base64",
                    "media_type": "application/pdf",
                    "data": base64.b64encode(pdf_file.read()).decode()
                }
            },
            {
                "type": "text",
                "text": CALCULATIONS_EXAMPLES if include_calculations else SIMPLE_EXAMPLES
            },
            {
                "type": "text",
                "text": prompt
            }
        ]
        pdf_file.seek(0)  # Reset file pointer

    # Send to Claude API
    message = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=8192,
        temperature=0,
        system="You are an expert utility bill analyst AI specializing in data extraction and standardization. Your primary responsibilities include:\n\n1. Accurately extracting specific fields from utility bills\n2. Handling complex cases such as tiered charges\n3. Maintaining consistent data formatting\n4. Returning data in a standardized JSON format\n\nYour expertise allows you to navigate complex billing structures, identify relevant information quickly, and standardize data in various utility bill formats. You are meticulous in following instructions and maintaining data integrity throughout the extraction and formatting process.",
        messages=[
            {
                "role": "user",
                "content": message_content
            }
        ]
    )

    # Store API usage statistics
    st.session_state.last_usage = {
        'input_tokens': message.usage.input_tokens,
        'output_tokens': message.usage.output_tokens,
        'stop_reason': message.stop_reason
    }

    # Store raw JSON response
    st.session_state.raw_json_response = message.model_dump_json()

    # Parse response
    response_data = json.loads(message.content[0].text)
    
    # Handle different response formats
    if isinstance(response_data, dict):
        response_data['filename'] = pdf_file.name
        result = response_data
    elif response_data.get('bills') and len(response_data['bills']) > 0:
        result = dict(zip(response_data['fields'], response_data['bills'][0]))
        result['filename'] = pdf_file.name
    else:
        raise ValueError("Unexpected response format from API")

    return result

def handle_processing_error(pdf_file, error, api_logs):
    """Handle errors during PDF processing.
    
    Args:
        pdf_file: The PDF file that caused the error
        error: The error that occurred
        api_logs: List to append the error log to
    """
    if 'problematic_files' not in st.session_state:
        st.session_state.problematic_files = []
    
    error_info = {
        'filename': pdf_file.name,
        'response': str(error)
    }
    
    if isinstance(error, json.JSONDecodeError):
        error_info['raw_response'] = st.session_state.get('raw_json_response', '')
    
    st.session_state.problematic_files.append(error_info)
    api_logs.append(log_api_call(pdf_file, None, str(error)))
    st.error(f"Error processing {pdf_file.name}: {str(error)}") 