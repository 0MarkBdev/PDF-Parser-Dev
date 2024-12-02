"""PDF parsing functionality for the PDF Parser application."""

import base64
import json
import io
import pandas as pd
import streamlit as st
from anthropic import Anthropic

from src.config.examples import CALCULATIONS_EXAMPLES, SIMPLE_EXAMPLES
from src.utils.api_utils import log_api_call

def process_pdf_files(uploaded_files, split_files, prompt, include_calculations):
    """Process PDF files through the Claude API.
    
    Args:
        uploaded_files: List of uploaded PDF files
        split_files: List of tuples (file_type, file_name, file_content) for split PDFs
        prompt: The prompt to send to Claude
        include_calculations: Whether to include calculations in the output
    
    Returns:
        DataFrame containing the extracted data
    """
    individual_results = []
    api_logs = []

    # Create the client with custom headers
    pdf_client = Anthropic(
        api_key=st.secrets["ANTHROPIC_API_KEY"],
        default_headers={"anthropic-beta": "pdfs-2024-09-25"}
    )

    # Process regular uploaded files
    for pdf_file in uploaded_files:
        try:
            result = process_single_pdf(pdf_client, pdf_file, prompt, include_calculations)
            if result:
                individual_results.append(result)
        except Exception as e:
            handle_processing_error(pdf_file, e, api_logs)

    # Process split PDFs
    for file_type, file_name, file_content in split_files:
        try:
            # Create a temporary BytesIO object to simulate a file upload
            temp_file = io.BytesIO(file_content)
            temp_file.name = file_name
            
            result = process_single_pdf(pdf_client, temp_file, prompt, include_calculations)
            if result:
                individual_results.append(result)
        except Exception as e:
            handle_processing_error(temp_file, e, api_logs)

    # Store API logs in session state
    st.session_state.api_logs = api_logs

    # Create DataFrame from results
    if individual_results:
        df = pd.DataFrame(individual_results)
        columns = ['filename'] + [col for col in df.columns if col != 'filename']
        return df[columns]
    
    return None

def process_single_pdf(client, pdf_file, prompt, include_calculations):
    """Process a single PDF file through the Claude API.
    
    Args:
        client: Anthropic client
        pdf_file: PDF file to process
        prompt: The prompt to send to Claude
        include_calculations: Whether to include calculations in the output
    
    Returns:
        Dict containing the extracted data
    """
    # Prepare message content for this PDF
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