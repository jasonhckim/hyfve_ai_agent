from modules import ai_description
from modules import google_drive
from modules import utils
import pandas as pd
import yaml
import gspread
from google.oauth2.service_account import Credentials
import pkg_resources

version = pkg_resources.get_distribution("google-api-python-client").version
print(f"google-api-python-client version: {version}")

# Ensure you import from submodules correctly
from googleapiclient.discovery import build  # ✅ This is the correct way
print("googleapiclient module imported successfully!")

# ✅ Load Configuration from YAML
with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

# ✅ Retrieve Folder IDs from Config
PDF_FOLDER_ID = config["drive_folder_ids"]["pdf"]
DOC_FOLDER_ID = config["drive_folder_ids"]["doc"]
CSV_FOLDER_ID = config["drive_folder_ids"]["csv"]

import os
if not os.path.exists("credentials.json"):
    print("❌ ERROR: credentials.json file is missing in GitHub Actions!")

# ✅ Google Sheets Credentials
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
SERVICE_ACCOUNT_FILE = "credentials.json"  # Ensure you have this in your project folder


def get_keywords_from_drive():
    """
    Fetches keywords from the latest document in Google Drive.

    NOTE: We must define or retrieve `doc_file` somewhere. 
    For example, you might do:

        doc_file = google_drive.list_files_in_drive(DOC_FOLDER_ID, "application/vnd.google-apps.document")
    
    so that `doc_file` is not None.
    """
    # Example: retrieve doc files from Drive (adjust to your needs):
    doc_file = google_drive.list_files_in_drive(DOC_FOLDER_ID, "application/vnd.google-apps.document")
    if not doc_file:
        return []

    # If we received a list of docs, handle the first one
    if isinstance(doc_file, list) and len(doc_file) > 0:
        doc_file = doc_file[0]
        doc_path = google_drive.download_file_from_drive(doc_file["id"], "keywords.txt")
        return utils.extract_keywords_from_doc(doc_path) if doc_path else []

    # If it's a single doc object, handle that
    if isinstance(doc_file, dict):
        doc_path = google_drive.download_file_from_drive(doc_file["id"], "keywords.txt")
        return utils.extract_keywords_from_doc(doc_path) if doc_path else []

    return []


def upload_to_google_sheets(df, pdf_filename, pdf_folder_id):
    """Uploads the DataFrame to a Google Sheet named after the PDF file and ensures it is moved to the correct Google Drive folder."""

    sheet_name = pdf_filename.replace(".pdf", "")

    # ✅ Authenticate with Google Sheets API
    print("🛠️ DEBUG: Authenticating with Google Sheets API...")
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    print("✅ Google Sheets API authentication successful.")

    # ✅ Try to open existing Google Sheet, otherwise create it
    try:
        print(f"🛠️ DEBUG: Checking if Google Sheet '{sheet_name}' already exists...")
        sheet = client.open(sheet_name)
        print(f"✅ Google Sheet '{sheet_name}' already exists.")
    except gspread.exceptions.SpreadsheetNotFound:
        print(f"🛠️ DEBUG: Google Sheet '{sheet_name}' not found, creating a new one...")
        sheet = client.create(sheet_name)
        print(f"✅ Created new Google Sheet: {sheet_name}")

    # ✅ Ensure the Google Sheet is moved to the correct Google Drive folder
    drive_service = build("drive", "v3", credentials=creds)  # Ensure proper API usage
    file_id = sheet.id  # Get the newly created sheet's ID

    print(f"🛠️ DEBUG: Moving Google Sheet '{sheet_name}' to folder: {pdf_folder_id}")

    try:
        drive_service.files().update(
            fileId=file_id,
            body={"parents": [pdf_folder_id]},
            fields="id, parents"
        ).execute()
    except Exception as e:
        print(f"❌ ERROR: Failed to move Google Sheet to folder {pdf_folder_id}. Details: {e}")

    # This always refers to the first sheet
    worksheet = sheet.sheet1
    if not worksheet:
        worksheet = sheet.add_worksheet(title="Sheet1", rows="1000", cols="10")

    # ✅ Convert DataFrame to list of lists for Google Sheets
    data = [df.columns.tolist()] + df.values.tolist()

    # ✅ Clear and update the sheet
    worksheet.clear()
    worksheet.update(values=data, range_name="A1")
    print(f"✅ Successfully uploaded data to Google Sheet '{sheet_name}'")


def process_pdf():
    """Extracts data from the latest PDF, generates descriptions, and uploads both files to Google Sheets."""

    # ✅ List all available PDFs before trying to download
    print("🛠️ DEBUG: Listing all PDFs in Google Drive folder...")
    pdf_files = google_drive.list_files_in_drive(PDF_FOLDER_ID, "application/pdf")

    if not pdf_files:
        print(f"❌ ERROR: No PDF files found in Google Drive folder '{PDF_FOLDER_ID}'.")
        return  # Stop if no files found

    # ✅ Debugging: Ensure 'f' is a dictionary before accessing keys
    print("🛠️ DEBUG: Available PDFs in Drive:")
    for f in pdf_files:
        if isinstance(f, dict):  # Ensure it's a dictionary before accessing keys
            print(f"     📄 Name: {f['name']} | 🆔 ID: {f['id']}")
        else:
            print(f"❌ ERROR: Unexpected data format for file: {f} (Type: {type(f)})")

    # ✅ Try to find 'test.pdf' (or any latest PDF)
    pdf_file = next((f for f in pdf_files if f["name"] == "test.pdf"), None)

    if not pdf_file:
        print("❌ ERROR: 'test.pdf' not found in Google Drive. Available PDFs are listed above.")
        return

    pdf_filename = pdf_file["name"]
    pdf_path = google_drive.download_file_from_drive(pdf_file["id"], pdf_filename)

    # ✅ Debugging: Check if the function returned a valid path
    if not pdf_path:
        print(f"❌ ERROR: google_drive.download_file_from_drive() returned None for '{pdf_filename}'")
        return  # Stop execution if the file is not downloaded

    # ✅ Debugging: Check if the file exists
    if not os.path.exists(pdf_path):
        print(f"❌ ERROR: PDF file '{pdf_filename}' was not downloaded successfully.")
        return  # Stop execution if the file is missing

    print(f"✅ Successfully downloaded '{pdf_filename}' to: {pdf_path}")

    # ✅ Extract Data from PDF
    extracted_data = google_drive.extract_text_and_images_from_pdf(pdf_path)

    # ✅ Debug: Check extracted data
    if not extracted_data:
        print("❌ ERROR: No data extracted from the PDF.")
        return

    # ✅ Fetch Keywords from Drive
    keywords = get_keywords_from_drive()

    # ✅ Generate descriptions
    processed_data = [
        ai_description.generate_description(entry["style_number"], entry["images"], keywords) 
        for entry in extracted_data
    ]

    # ✅ Convert to DataFrame
    df = pd.DataFrame(processed_data)

    # ✅ Debug: Check available columns before filtering
    print("🛠️ DEBUG: Available columns in DataFrame:", df.columns.tolist())

    # ✅ Safely reindex to expected columns
    expected_columns = [
        "Style Number", "Product Title", "Product Description", "Tags", 
        "Product Category", "Product Type", "Option2 Value", "Keywords"
    ]
    df = df.reindex(columns=expected_columns, fill_value="N/A")  # Prevents KeyError

    # ✅ Upload the data to Google Sheets
    print("🛠️ DEBUG: Uploading data to Google Sheets...")
    upload_to_google_sheets(df, pdf_filename, PDF_FOLDER_ID)

    print(f"✅ Process completed. PDF and Google Sheet are in the same folder: {PDF_FOLDER_ID}")


if __name__ == "__main__":
    process_pdf()
