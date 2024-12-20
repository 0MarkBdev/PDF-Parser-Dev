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

def render_debug_tab(uploaded_files, prompt, include_calculations, client):
    """Render the debug tab UI.
    
    Args:
        uploaded_files: List of uploaded PDF files
        prompt: The prompt to send to Claude
        include_calculations: Whether to include calculations in the output
        client: Anthropic client instance
    """
    # Create sections using expanders
    with st.expander("🖼️ Image Processing Debug", expanded=True):
        st.write("Upload a PDF to see intermediate steps of image processing")
        debug_pdf = st.file_uploader("Upload PDF for image debug", type=['pdf'])
        
        if debug_pdf:
            if st.button("Process and Download Images"):
                # Convert PDF to initial image
                images_data = convert_pdf_to_image(debug_pdf, use_png=True)
                
                for page_num, (img_base64, _) in enumerate(images_data, 1):
                    st.markdown(f"### Page {page_num}")
                    
                    # Get original image
                    img_bytes = base64.b64decode(img_base64)
                    original_image = Image.open(io.BytesIO(img_bytes))
                    
                    # Convert to OpenCV format
                    cv_image = cv2.cvtColor(np.array(original_image), cv2.COLOR_RGB2BGR)
                    
                    # Get grayscale
                    gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
                    
                    # Get binary image
                    binary = cv2.adaptiveThreshold(
                        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2
                    )
                    
                    # Get final optimized image
                    optimized = optimize_image_for_processing(original_image)
                    
                    # Create columns for download buttons
                    cols = st.columns(5)
                    
                    # Prepare download buttons for each stage
                    with cols[0]:
                        original_bytes = save_debug_image(original_image)
                        st.download_button(
                            "Original",
                            original_bytes,
                            f"page_{page_num}_original.png",
                            "image/png"
                        )
                    
                    with cols[1]:
                        cv_bytes = save_debug_image(cv_image)
                        st.download_button(
                            "RGB",
                            cv_bytes,
                            f"page_{page_num}_rgb.png",
                            "image/png"
                        )
                    
                    with cols[2]:
                        gray_bytes = save_debug_image(gray)
                        st.download_button(
                            "Grayscale",
                            gray_bytes,
                            f"page_{page_num}_gray.png",
                            "image/png"
                        )
                    
                    with cols[3]:
                        binary_bytes = save_debug_image(binary)
                        st.download_button(
                            "Binary",
                            binary_bytes,
                            f"page_{page_num}_binary.png",
                            "image/png"
                        )
                    
                    with cols[4]:
                        optimized_bytes = save_debug_image(optimized)
                        st.download_button(
                            "Optimized",
                            optimized_bytes,
                            f"page_{page_num}_optimized.png",
                            "image/png"
                        )
                    
                    # Show preview of images
                    preview_cols = st.columns(5)
                    with preview_cols[0]:
                        st.image(original_bytes, caption="Original")
                    with preview_cols[1]:
                        st.image(cv_bytes, caption="RGB")
                    with preview_cols[2]:
                        st.image(gray_bytes, caption="Grayscale")
                    with preview_cols[3]:
                        st.image(binary_bytes, caption="Binary")
                    with preview_cols[4]:
                        st.image(optimized_bytes, caption="Optimized")
                    
                    st.markdown("---")
        else:
            st.info("Upload a PDF file to see the intermediate image processing steps")

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
    
    with st.expander("📊 Last API Call Statistics", expanded=False):
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
    
    with st.expander("📝 Raw JSON Response", expanded=False):
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