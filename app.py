import streamlit as st
import pandas as pd
from anthropic import Anthropic
import base64
import json

# Add password protection
def check_password():
    """Returns `True` if the user had the correct password."""
    if "password_correct" not in st.session_state:
        st.text_input(
            "Please enter the password",
            type="password",
            key="password",
            on_change=password_entered
        )
        return False
    return st.session_state["password_correct"]

def password_entered():
    """Checks whether a password entered by the user is correct."""
    if st.session_state["password"] == st.secrets["password"]:
        st.session_state["password_correct"] = True
        del st.session_state["password"]
    else:
        st.session_state["password_correct"] = False

# Main app
def main():
    # Get API key from secrets
    client = Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])

    # Create the interface
    st.title('Bill Parser')

    # Define the fields you want to extract
    default_prompt = """Please extract the following information from this utility bill and return it in a JSON format with these exact keys (if there are two instances of a field, create a new one by adding a 2 after):
    {
        "bill_date": "YYYY-MM-DD",
        "due_date": "YYYY-MM-DD",
        "account_number": "",
        "total_amount_due": "",
        "service_address": "",
        "Sewer Consumption Charge": "",
        "Water Consumption Charge": ""
    }

    Please ensure:
    1. Dates are in YYYY-MM-DD format
    2. Remove any currency symbols from total_amount_due
    3. Return ONLY the JSON object, no additional text
    4. If a field is not found, use null instead of leaving it empty
    5. If there are two instances of a field, create a new one by adding a 2 after"""

    # Add a text area for customizing the extraction instructions
    prompt = st.text_area(
        "What should I extract from these bills?",
        value=default_prompt,
        height=300
    )

    # Add file uploader
    uploaded_files = st.file_uploader("Upload PDF Bills", type=['pdf'], accept_multiple_files=True)

    if st.button('Process Bills'):
        if uploaded_files:
            all_results = []
            progress_bar = st.progress(0)
            status_text = st.empty()

            for idx, pdf in enumerate(uploaded_files):
                try:
                    status_text.text(f"Processing {pdf.name}...")

                    # Create the client with custom headers for each request
                    pdf_client = Anthropic(
                        api_key=st.secrets["ANTHROPIC_API_KEY"],
                        default_headers={"anthropic-beta": "pdfs-2024-09-25"}
                    )

                    # Send to Claude API
                    message = pdf_client.messages.create(
                        model="claude-3-5-sonnet-20241022",
                        max_tokens=1024,
                        messages=[
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "document",
                                        "source": {
                                            "type": "base64",
                                            "media_type": "application/pdf",
                                            "data": base64.b64encode(pdf.read()).decode()
                                        }
                                    },
                                    {"type": "text", "text": prompt}
                                ]
                            }
                        ]
                    )

                    # Parse the JSON response
                    try:
                        extracted_data = json.loads(message.content[0].text)
                        # Add filename to the extracted data
                        extracted_data['filename'] = pdf.name
                        all_results.append(extracted_data)
                    except json.JSONDecodeError as je:
                        st.warning(f"Could not parse JSON from {pdf.name}. Raw response: {message.content[0].text}")
                        continue

                    # Update progress
                    progress_bar.progress((idx + 1) / len(uploaded_files))

                except Exception as e:
                    st.error(f"Error processing {pdf.name}: {str(e)}")

            if all_results:
                # Convert to DataFrame
                df = pd.DataFrame(all_results)

                # Reorder columns to put filename first
                columns = ['filename'] + [col for col in df.columns if col != 'filename']
                df = df[columns]

                # Convert to Excel
                excel_buffer = pd.ExcelWriter('results.xlsx', engine='openpyxl')
                df.to_excel(excel_buffer, index=False, sheet_name='Extracted Data')

                # Auto-adjust column widths
                worksheet = excel_buffer.sheets['Extracted Data']
                for idx, col in enumerate(df.columns):
                    max_length = max(
                        df[col].astype(str).apply(len).max(),
                        len(str(col))
                    )
                    worksheet.column_dimensions[chr(65 + idx)].width = max_length + 2

                excel_buffer.close()

                # Add download button
                with open('results.xlsx', 'rb') as f:
                    st.download_button(
                        'Download Results',
                        f,
                        'results.xlsx',
                        mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                    )

                # Also display the results in the app
                st.write("### Extracted Data")
                st.dataframe(df)

# Run the app with password protection
if check_password():
    main()
else:
    st.stop()