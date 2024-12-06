"""PDF splitting functionality for the PDF Parser application."""

import os
import fitz  # PyMuPDF
import streamlit as st

def split_pdf(uploaded_pdf, group_ranges, output_dir=None):
    """Split a PDF into multiple PDFs based on page ranges.
    
    Args:
        uploaded_pdf: The uploaded PDF file
        group_ranges: List of tuples containing (group_name, [(start, end), ...])
        output_dir: Directory to save split PDFs (defaults to current directory)
    
    Returns:
        List of created PDF filenames
    """
    if output_dir is None:
        output_dir = os.getcwd()
        
    created_files = []
    
    try:
        # Save the uploaded PDF temporarily
        temp_path = os.path.join(output_dir, uploaded_pdf.name)
        with open(temp_path, "wb") as f:
            f.write(uploaded_pdf.getvalue())
        
        # Create new PDFs for each group
        for group_name, valid_ranges in group_ranges:
            pdf_document = fitz.open(temp_path)
            new_pdf = fitz.open()
            
            all_pages = []
            for start, end in valid_ranges:
                all_pages.extend(range(start-1, end))
            
            for page_num in sorted(all_pages):
                new_pdf.insert_pdf(pdf_document, from_page=page_num, to_page=page_num)
            
            # Generate filename using group name
            base_name = os.path.splitext(uploaded_pdf.name)[0]
            ranges_str = '_'.join(f"{start}-{end}" for start, end in valid_ranges)
            safe_group_name = "".join(c if c.isalnum() else "_" for c in group_name)
            new_filename = f"split_{safe_group_name}_{ranges_str}_{base_name}.pdf"
            new_path = os.path.join(output_dir, new_filename)
            
            # Save the new PDF
            new_pdf.save(new_path)
            new_pdf.close()
            pdf_document.close()
            
            created_files.append(new_filename)
            
    except Exception as e:
        raise Exception(f"Error splitting PDF: {str(e)}")
        
    return created_files

def validate_page_ranges(ranges, total_pages):
    """Validate page ranges against total number of pages.
    
    Args:
        ranges: List of (start, end) tuples
        total_pages: Total number of pages in the PDF
    
    Returns:
        (valid_ranges, error_messages)
    """
    valid_ranges = []
    error_messages = []
    
    for start, end in ranges:
        try:
            start_num = int(start)
            end_num = int(end)
            
            if start_num < 1 or end_num > total_pages:
                error_messages.append(
                    f"Range {start}-{end} is outside valid pages (1-{total_pages})")
            elif start_num > end_num:
                error_messages.append(
                    f"Range {start}-{end} is invalid (start > end)")
            else:
                valid_ranges.append((start_num, end_num))
        except ValueError:
            error_messages.append(
                f"Invalid numbers in range {start}-{end}")
    
    return valid_ranges, error_messages

def get_pdf_page_count(uploaded_pdf):
    """Get the total number of pages in a PDF.
    
    Args:
        uploaded_pdf: The uploaded PDF file
    
    Returns:
        int: Total number of pages
    """
    # Save the uploaded PDF temporarily
    temp_path = os.path.join(os.getcwd(), uploaded_pdf.name)
    with open(temp_path, "wb") as f:
        f.write(uploaded_pdf.getvalue())
    
    # Open PDF and get page count
    pdf_document = fitz.open(temp_path)
    page_count = len(pdf_document)
    pdf_document.close()
    
    return page_count 