"""API utility functions for the PDF Parser application."""

import base64
import json
import math
import streamlit as st
from datetime import datetime
from typing import Any

from src.config.examples import CALCULATIONS_EXAMPLES, SIMPLE_EXAMPLES

def preview_api_call(uploaded_files, prompt, include_calculations, use_vision=False):
    """Generate a preview of the API call that would be sent"""
    # Show preview for first file only since files are processed individually
    if not uploaded_files:
        return "Upload files to see API call preview"
    
    pdf_file = uploaded_files[0]
    
    # Actually encode the PDF content for the preview
    pdf_base64 = base64.b64encode(pdf_file.read()).decode()
    pdf_file.seek(0)  # Reset file pointer after reading
    
    # Prepare message content for single PDF
    message_content = [
        {
            "type": "image" if use_vision else "document",
            "source": {
                "type": "base64",
                "media_type": "image/png" if use_vision else "application/pdf",
                "data": pdf_base64  # Use actual encoded content instead of placeholder
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

    # Construct the full API call preview
    api_call_preview = {
        "model": "claude-3-5-sonnet-20241022",
        "max_tokens": 8192,
        "temperature": 0,
        "system": "You are an expert utility bill analyst AI specializing in data extraction and standardization. Your primary responsibilities include:\n\n1. Accurately extracting specific fields from utility bills\n2. Handling complex cases such as tiered charges\n3. Maintaining consistent data formatting\n4. Returning data in a standardized JSON format\n\nYour expertise allows you to navigate complex billing structures, identify relevant information quickly, and standardize data in various utility bill formats. You are meticulous in following instructions and maintaining data integrity throughout the extraction and formatting process.",
        "messages": [
            {
                "role": "user",
                "content": message_content
            }
        ]
    }
    
    return {
        "note": "Preview for first file only. Each file is processed individually.",
        "file_being_previewed": pdf_file.name,
        "api_call": api_call_preview
    }

def count_tokens(client, prompt, include_calculations):
    """Generate a token count for the API call without PDFs"""
    # Prepare message content without PDFs
    message_content = [
        {
            "type": "text",
            "text": CALCULATIONS_EXAMPLES if include_calculations else SIMPLE_EXAMPLES
        },
        {
            "type": "text",
            "text": prompt
        }
    ]
    
    try:
        # Use the client's direct request method
        response = client._client.post(
            "https://api.anthropic.com/v1/messages/count_tokens",
            json={
                "model": "claude-3-5-sonnet-20241022",
                "system": "You are an expert utility bill analyst AI specializing in data extraction and standardization. Your primary responsibilities include:\n\n1. Accurately extracting specific fields from utility bills\n2. Handling complex cases such as tiered charges and multiple instances of the same charge\n3. Maintaining consistent data formatting\n4. Returning data in a standardized JSON format\n\nYour expertise allows you to navigate complex billing structures, identify relevant information quickly, and standardize data in various utility bill formats. You are meticulous in following instructions and maintaining data integrity throughout the extraction and formatting process.",
                "messages": [
                    {
                        "role": "user",
                        "content": message_content
                    }
                ],
                "tools": []  # Include empty tools array as per spec
            },
            headers={
                "x-api-key": st.secrets["ANTHROPIC_API_KEY"],
                "anthropic-beta": "token-counting-2024-11-01",
                "anthropic-version": "2023-06-01"
            }
        )
        
        # Print response for debugging
        print("API Response:", response.text)
        
        result = response.json()
        
        # Return the raw result instead of trying to access input_tokens
        return result
        
    except Exception as e:
        # Wrap any errors with more context
        raise Exception(f"Token counting API error: {str(e)}") from e

def calculate_pdf_tokens(pdf_file) -> int:
    """Estimate token count for a PDF based on file size"""
    pdf_size_kb = len(pdf_file.read()) / 1024  # Convert bytes to KB
    pdf_file.seek(0)  # Reset file pointer
    return math.ceil(pdf_size_kb * 75)  # 75 tokens per KB

def log_api_call(file: Any, response: Any, error: str = None) -> dict:
    """Log an API call and its response"""
    return {
        "timestamp": datetime.now().isoformat(),
        "file_processed": file.name,
        "response": response,
        "error": error
    } 