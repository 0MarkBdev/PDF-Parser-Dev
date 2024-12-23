"""Debug tab UI component for the PDF Parser application."""

import json
import streamlit as st
from src.utils.api_utils import preview_api_call, count_tokens
import io
from PIL import Image
import cv2
import numpy as np
from src.pdf.parser import convert_pdf_to_image, optimize_image_for_processing
import base64

def save_debug_image(image, format='PNG'):
    """Save image to bytes for downloading."""
    img_byte_arr = io.BytesIO()
    if isinstance(image, np.ndarray):
        # Convert OpenCV image to PIL
        if len(image.shape) == 2:  # Grayscale
            pil_image = Image.fromarray(image)
        else:  # BGR to RGB
            pil_image = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
    else:
        pil_image = image
    pil_image.save(img_byte_arr, format=format)
    return img_byte_arr.getvalue()

def process_debug_images(debug_pdf):
    """Process PDF and store debug images in session state."""
    images_data = convert_pdf_to_image(debug_pdf, use_png=True, skip_optimization=True)  # Skip optimization to get true original
    debug_images = []
    
    for page_num, (img_base64, _) in enumerate(images_data, 1):
        # Get original image
        img_bytes = base64.b64decode(img_base64)
        original_image = Image.open(io.BytesIO(img_bytes))
        
        # Convert to OpenCV format
        cv_image = cv2.cvtColor(np.array(original_image), cv2.COLOR_RGB2BGR)
        
        # Get grayscale
        gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
        
        # Apply Gaussian blur to reduce noise
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        
        # Get binary image with more aggressive thresholding
        binary = cv2.adaptiveThreshold(
            blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 21, 15
        )
        
        # Remove noise with morphological operations
        kernel = np.ones((3,3), np.uint8)
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
        
        # Find contours for visualization
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Filter out very small contours (noise)
        min_contour_area = cv_image.shape[0] * cv_image.shape[1] * 0.002  # Increased from 0.0001 (0.01%) to 0.002 (0.2%)
        contours = [cnt for cnt in contours if cv2.contourArea(cnt) > min_contour_area]
        
        # Create a copy of original image for contour visualization
        contour_viz = cv_image.copy()
        
        # Find the bounding box that contains all content
        if contours:
            # Initialize with first contour
            x_min, y_min, x_max, y_max = float('inf'), float('inf'), 0, 0
            
            # Draw all contours in red with thicker lines
            cv2.drawContours(contour_viz, contours, -1, (0, 0, 255), 2)
            
            for contour in contours:
                x, y, w, h = cv2.boundingRect(contour)
                x_min = min(x_min, x)
                y_min = min(y_min, y)
                x_max = max(x_max, x + w)
                y_max = max(y_max, y + h)
            
            # Add smaller padding (1% of image size)
            padding_x = int(cv_image.shape[1] * 0.01)
            padding_y = int(cv_image.shape[0] * 0.01)
            
            x_min = max(0, x_min - padding_x)
            y_min = max(0, y_min - padding_y)
            x_max = min(cv_image.shape[1], x_max + padding_x)
            y_max = min(cv_image.shape[0], y_max + padding_y)
            
            # Draw the final bounding box in bright green with thicker line
            cv2.rectangle(contour_viz, (x_min, y_min), (x_max, y_max), (0, 255, 0), 3)
        else:
            # If no contours found, use the whole image
            x_min, y_min = 0, 0
            x_max, y_max = cv_image.shape[1], cv_image.shape[0]
        
        # Create cropped image
        cropped = cv_image[y_min:y_max, x_min:x_max]
        optimized = Image.fromarray(cv2.cvtColor(cropped, cv2.COLOR_BGR2RGB))
        
        # Convert binary to 3 channels for better visualization
        binary_viz = cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)
        
        # Store all versions
        page_images = {
            'original': save_debug_image(original_image),
            'rgb': save_debug_image(cv_image),
            'gray': save_debug_image(gray),
            'binary': save_debug_image(binary_viz),
            'contours': save_debug_image(contour_viz),
            'optimized': save_debug_image(optimized)
        }
        debug_images.append(page_images)
    
    return debug_images

def render_debug_tab(uploaded_files, prompt, include_calculations, client):
    """Render the debug tab UI."""
    st.markdown("## Image Processing Debug")
    st.write("Upload a PDF to see intermediate steps of image processing")
    
    # Initialize session state for debug images if not exists
    if 'debug_images' not in st.session_state:
        st.session_state.debug_images = None
    
    debug_pdf = st.file_uploader("Upload PDF for image debug", type=['pdf'], key="debug_pdf_uploader")
    
    if debug_pdf:
        if st.button("Process and Download Images", key="process_images_btn"):
            with st.spinner("Processing images..."):
                st.session_state.debug_images = process_debug_images(debug_pdf)
    
    # Display images if they exist in session state
    if st.session_state.debug_images:
        for page_num, page_images in enumerate(st.session_state.debug_images, 1):
            st.markdown(f"### Page {page_num}")
            
            cols = st.columns(6)  # Changed to 6 columns
            
            with cols[0]:
                st.download_button(
                    "Download Original",
                    page_images['original'],
                    f"page_{page_num}_original.png",
                    "image/png",
                    key=f"download_original_{page_num}"
                )
                st.image(page_images['original'], caption="Original", use_column_width=True)
            
            with cols[1]:
                st.download_button(
                    "Download RGB",
                    page_images['rgb'],
                    f"page_{page_num}_rgb.png",
                    "image/png",
                    key=f"download_rgb_{page_num}"
                )
                st.image(page_images['rgb'], caption="RGB", use_column_width=True)
            
            with cols[2]:
                st.download_button(
                    "Download Grayscale",
                    page_images['gray'],
                    f"page_{page_num}_gray.png",
                    "image/png",
                    key=f"download_gray_{page_num}"
                )
                st.image(page_images['gray'], caption="Grayscale", use_column_width=True)
            
            with cols[3]:
                st.download_button(
                    "Download Binary",
                    page_images['binary'],
                    f"page_{page_num}_binary.png",
                    "image/png",
                    key=f"download_binary_{page_num}"
                )
                st.image(page_images['binary'], caption="Binary (White = Content)", use_column_width=True)
            
            with cols[4]:
                st.download_button(
                    "Download Contours",
                    page_images['contours'],
                    f"page_{page_num}_contours.png",
                    "image/png",
                    key=f"download_contours_{page_num}"
                )
                st.image(page_images['contours'], caption="Detected Content (Red: Details, Green: Final Crop)", use_column_width=True)
            
            with cols[5]:
                st.download_button(
                    "Download Optimized",
                    page_images['optimized'],
                    f"page_{page_num}_optimized.png",
                    "image/png",
                    key=f"download_optimized_{page_num}"
                )
                st.image(page_images['optimized'], caption="Final Cropped Result", use_column_width=True)
            
            st.markdown("---")
    elif debug_pdf:
        st.info("Click 'Process and Download Images' to see the processing steps")
    else:
        st.info("Upload a PDF file to see the intermediate image processing steps")

    st.markdown("---")

    # Original debug sections
    with st.expander("📤 API Call Preview", expanded=True):
        st.write("Preview the API call that will be sent when processing files")
        
        if uploaded_files:
            col1, col2 = st.columns([1, 1])
            
            # Create buttons side by side but keep display area unified
            preview_clicked = col1.button("Generate API Call Preview")
            count_tokens_clicked = col2.button("Preview Api Call & Count Tokens")
            
            if preview_clicked or count_tokens_clicked:
                # If token counting was requested, show it first
                if count_tokens_clicked:
                    try:
                        token_count = count_tokens(client, prompt, include_calculations)
                        st.success("Token Count Results:")
                        # Print the full response for debugging
                        print("Token count response:", token_count)
                        st.json(token_count)  # Show the full response
                        st.info("Note: This count excludes PDF content as it's not yet supported by the token counting API")
                    except Exception as e:
                        st.error(f"Error counting tokens: {str(e)}")
                        st.error("Please check the API documentation or try again later.")
                    
                    # Add a visual separator
                    st.markdown("---")
                
                # Show the API preview (same for both buttons)
                preview = preview_api_call(uploaded_files, prompt, include_calculations)
                st.session_state.api_preview = preview
                st.json(preview)
        else:
            st.info("Upload files in the main tab to preview the API call")
    
    with st.expander("���� Last API Call Statistics", expanded=False):
        if hasattr(st.session_state, 'last_usage'):
            st.write("Last API Call Statistics:")
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Input Tokens", st.session_state.last_usage['input_tokens'])
            with col2:
                st.metric("Output Tokens", st.session_state.last_usage['output_tokens'])
            
            # Add stop reason explanation
            stop_reason = st.session_state.last_usage['stop_reason']
            explanation = {
                "end_turn": "The model completed its response naturally.",
                "max_tokens": "The response was cut off due to reaching the token limit.",
                "stop_sequence": "The model stopped at a designated stop sequence.",
                "error": "The response was terminated due to an error."
            }.get(stop_reason, f"Unknown stop reason: {stop_reason}")
            
            st.write("**Stop Reason:**")
            st.info(explanation)
        else:
            st.write("No API calls made yet.")
    
    with st.expander("�� Raw JSON Response", expanded=False):
        if hasattr(st.session_state, 'raw_json_response'):
            st.write("Raw JSON Response from last API call:")
            # Parse the JSON string and then format it nicely
            try:
                formatted_json = json.dumps(json.loads(st.session_state.raw_json_response), indent=2)
                st.code(formatted_json, language='json')
            except json.JSONDecodeError:
                # Fallback to raw display if JSON parsing fails
                st.code(st.session_state.raw_json_response, language='json')
        else:
            st.write("No API response data available yet.")

    with st.expander("📋 API Call Logs", expanded=True):
        if hasattr(st.session_state, 'api_logs') and st.session_state.api_logs:
            for log in st.session_state.api_logs:
                st.markdown(f"### File: {log['file_processed']}")
                st.markdown("**Timestamp:**")
                st.write(log['timestamp'])
                
                if log['error']:
                    st.error(f"**Error:** {log['error']}")
                else:
                    st.markdown("**Number of Bills Returned:**")
                    st.write(log['response']['num_bills_returned'])
                    st.markdown("**Fields Returned:**")
                    st.write(log['response']['fields_returned'])
                    
                    # Use tabs instead of nested expanders
                    raw_tab, parsed_tab = st.tabs(["Raw Response", "Parsed Response"])
                    
                    with raw_tab:
                        st.json(log['response']['raw_response'])
                    
                    with parsed_tab:
                        st.json(log['response']['parsed_response'])
                    
                # Add a visual separator between files
                st.markdown("---")
        else:
            st.info("No API calls logged yet.")

    with st.expander("⚠️ Problematic Files", expanded=True):
        if hasattr(st.session_state, 'problematic_files') and st.session_state.problematic_files:
            for file_log in st.session_state.problematic_files:
                st.markdown(f"### File: {file_log['filename']}")
                st.markdown("**Response data:**")
                st.json(file_log['response'])
                st.markdown("---")
        else:
            st.info("No problematic files detected in the last processing run.") 