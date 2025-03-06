import os
import yaml
from googleapiclient.discovery import build
from google.oauth2 import service_account
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
import fitz  # PyMuPDF
from PIL import Image
import io
import base64
import re

# ✅ Load Configuration from YAML
with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

# ✅ Retrieve Folder IDs from Config
PDF_FOLDER_ID = config["drive_folder_ids"]["pdf"]
DOC_FOLDER_ID = config["drive_folder_ids"]["doc"]
CSV_FOLDER_ID = config["drive_folder_ids"]["csv"]

# ✅ Set Google Cloud credentials
SCOPES = ["https://www.googleapis.com/auth/drive"]
SERVICE_ACCOUNT_FILE = "credentials.json"
creds = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
drive_service = build("drive", "v3", credentials=creds)

def list_files_in_drive(folder_id, mime_type):
    """Lists the most recent file of a given type in a Google Drive folder."""
    query = f"'{folder_id}' in parents and mimeType='{mime_type}'"
    results = drive_service.files().list(q=query, orderBy="createdTime desc", fields="files(id, name)").execute()
    files = results.get("files", [])
    
    return files[0] if files else None

def download_file_from_drive(file_id, filename):
    """Downloads a file from Google Drive."""
    file_path = f"/mnt/data/{filename}"
    
    try:
        request = drive_service.files().get_media(fileId=file_id)
        with open(file_path, "wb") as file:
            downloader = MediaIoBaseDownload(file, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()

        return file_path
    except Exception as e:
        print(f"❌ ERROR: Failed to download {filename}. Debug: {e}")
        return None

def upload_file_to_drive(file_path, folder_id):
    """Uploads a file to Google Drive inside the specified folder."""
    file_metadata = {
        "name": file_path.split("/")[-1],  # Extracts filename
        "parents": [folder_id]
    }
    media = MediaFileUpload(file_path, resumable=True)

    uploaded_file = drive_service.files().create(
        body=file_metadata,
        media_body=media,
        fields="id"
    ).execute()

    print(f"✅ Uploaded CSV to Google Drive: https://drive.google.com/file/d/{uploaded_file['id']}")
    return uploaded_file["id"]

def extract_text_and_images_from_pdf(pdf_path):
    """Extracts both text and images from a PDF."""
    doc = fitz.open(pdf_path)
    extracted_data = []
    style_regex = r"\b(DZ\d{2}[A-Z]\d{3,5}(-SET|-D)?|HF\d{2}[A-Z]\d{3,5}(-SET|-D)?)\b"

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text")
        images = []

        for img_index, img in enumerate(page.get_images(full=True)):
            xref = img[0]
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            image = Image.open(io.BytesIO(image_bytes))
            img_io = io.BytesIO()
            image.save(img_io, format="JPEG")
            img_base64 = base64.b64encode(img_io.getvalue()).decode("utf-8")
            images.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_base64}"}})

        style_number = re.findall(style_regex, text)
        style_number = style_number[0][0] if style_number else "Unknown"

        extracted_data.append({
            "page": page_num + 1,
            "style_number": style_number,
            "text": text.strip(),
            "images": images
        })

    return extracted_data
