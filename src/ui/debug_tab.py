"""Debug tab UI component for the PDF Parser application."""

import json
import base64
import streamlit as st
from src.utils.api_utils import preview_api_call
from src.pdf.parser import convert_pdf_to_image
from src.config.examples import CALCULATIONS_EXAMPLES, SIMPLE_EXAMPLES

def count_tokens(client, prompt, include_calculations, uploaded_files=None, use_vision=False):
    """Count tokens for the API call.
    
    Args:
        client: Anthropic client instance
        prompt: The prompt text
        include_calculations: Whether to include calculations
        uploaded_files: List of uploaded PDF files
        use_vision: Whether to process PDFs as images
    """
    messages = []
    
    if uploaded_files and use_vision:
        # Convert first PDF to image and include it in token count
        pdf_file = uploaded_files[0]
        img_data = convert_pdf_to_image(pdf_file)
        
        messages.append({
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": img_data
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
        })
    else:
        # Regular token counting without PDF/image content
        messages.append({
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": CALCULATIONS_EXAMPLES if include_calculations else SIMPLE_EXAMPLES
                },
                {
                    "type": "text",
                    "text": prompt
                }
            ]
        })
    
    response = client.beta.messages.count_tokens(
        betas=["token-counting-2024-11-01"],
        model="claude-3-5-sonnet-20241022",
        messages=messages
    )
    
    return response.json()

def render_debug_tab(uploaded_files, prompt, include_calculations, client):
    """Render the debug tab UI.
    
    Args:
        uploaded_files: List of uploaded PDF files
        prompt: The prompt to send to Claude
        include_calculations: Whether to include calculations in the output
        client: Anthropic client instance
    """
    # Get vision mode from session state
    use_vision = st.session_state.get('use_vision', False)
    
    # Create sections using expanders
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
                        token_count = count_tokens(client, prompt, include_calculations, uploaded_files, use_vision)
                        st.success("Token Count Results:")
                        st.json(token_count)
                        if not use_vision:
                            st.info("Note: PDF content is excluded from token counting. Enable vision mode to include the first page as an image in the count.")
                    except Exception as e:
                        st.error(f"Error counting tokens: {str(e)}")
                        st.error("Please check the API documentation or try again later.")
                    
                    # Add a visual separator
                    st.markdown("---")
                
                # Show the API preview (same for both buttons)
                preview = preview_api_call(uploaded_files, prompt, include_calculations, use_vision)
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