import fitz  # PyMuPDF
from PIL import Image
import io
import openai
import pandas as pd
import re
import json
import base64
import os
import time
import pytesseract
import cv2
import numpy as np
from googleapiclient.discovery import build
from google.oauth2 import service_account
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
import yaml

# ✅ Load API key from config.yaml
with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

# ✅ Use API key from ENV, but fallback to config.yaml
openai.api_key = os.getenv("OPENAI_API_KEY", config.get("openai_api_key"))

# 🔍 Debugging: Print first few characters of the key
if openai.api_key and openai.api_key.startswith("sk-"):
    print(f"✅ OpenAI API Key Loaded: {openai.api_key[:10]}********")
else:
    print("❌ ERROR: OpenAI API Key is missing or incorrect!")
    exit()

# ✅ Set Google Cloud credentials
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "C:/hyfve_ai_agent/credentials.json"

# ✅ Load Google API credentials
SCOPES = ["https://www.googleapis.com/auth/drive"]
SERVICE_ACCOUNT_FILE = "credentials.json"
creds = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)

drive_service = build("drive", "v3", credentials=creds)

def upload_file_to_drive(file_path, folder_id):
    """Uploads a file to Google Drive inside the specified folder."""
    file_metadata = {
        "name": file_path.split("/")[-1],  # Extracts filename
        "parents": [folder_id]  # ✅ Uploads inside the same folder as the PDF
    }
    media = MediaFileUpload(file_path, resumable=True)

    uploaded_file = drive_service.files().create(
        body=file_metadata,
        media_body=media,
        fields="id"
    ).execute()

    print(f"✅ Uploaded CSV to Google Drive: https://drive.google.com/file/d/{uploaded_file['id']}")
    return uploaded_file["id"]

# ✅ Google Drive Folder IDs
PDF_FOLDER_ID = "1YrYWjpWUmGN-ISJK0TrO66SirBsLeMcH"
DOC_FOLDER_ID = "1Ja_3axmjpBO0pTImZiGNFF4qEtgPt50z"
CSV_UPLOAD_FOLDER_ID = PDF_FOLDER_ID  # Save CSV in the same folder as the PDF

# ✅ Regex for style numbers (DZ & HF)
STYLE_REGEX = r"\b(DZ\d{2}[A-Z]\d{3,5}(-SET|-D)?|HF\d{2}[A-Z]\d{3,5}(-SET|-D)?)\b"

def list_files_in_drive(folder_id, mime_type):
    """Lists the most recent file of a given type (PDF, DOCX, Google Docs) in a Google Drive folder."""
    query = f"'{folder_id}' in parents and mimeType='{mime_type}'"
    results = drive_service.files().list(q=query, orderBy="createdTime desc", fields="files(id, name, mimeType)").execute()
    files = results.get("files", [])

    if not files:
        print(f"❌ No {mime_type} files found in Google Drive folder {folder_id}!")
        return None

    latest_file = files[0]  # ✅ Get the most recent file only
    print(f"✅ Found file: {latest_file['name']} ({latest_file['mimeType']})")
    return latest_file

def download_file_from_drive(file_id, filename, file_type="pdf"):
    """Downloads a file from Google Drive."""
    file_path = f"/mnt/data/{filename}"  # Temporary storage

    try:
        if file_type == "pdf":
            request = drive_service.files().get_media(fileId=file_id)
            with open(file_path, "wb") as file:
                downloader = MediaIoBaseDownload(file, request)
                done = False
                while not done:
                    _, done = downloader.next_chunk()
        else:
            request = drive_service.files().export(fileId=file_id, mimeType="text/plain")
            with open(file_path, "wb") as file:
                file.write(request.execute())

        print(f"✅ Downloaded file: {filename} to {file_path}")
        return file_path

    except Exception as e:
        print(f"❌ ERROR: Failed to download {filename}. Debug: {e}")
        return None

def extract_style_number_from_text(text):
    """Extracts the style number from PDF text."""
    matches = re.findall(STYLE_REGEX, text)
    if matches:
        style_number = matches[0][0]  # ✅ Get first match
        print(f"✅ Found Style Number: {style_number}")
        return style_number
    else:
        print("⚠️ No valid style number found!")
        return "Unknown"

def extract_text_and_images_from_pdf(pdf_path):
    """Extracts both text and images from a PDF."""
    doc = fitz.open(pdf_path)
    extracted_data = []

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

        style_number = extract_style_number_from_text(text)

        extracted_data.append({
            "page": page_num + 1,
            "style_number": style_number,
            "text": text.strip(),
            "images": images
        })

    return extracted_data

def clean_json(response_text):
    """Removes Markdown code block formatting and extra spaces."""
    response_text = response_text.strip()

    # If response is wrapped in triple backticks, remove them
    if response_text.startswith("```json") and response_text.endswith("```"):
        response_text = re.sub(r"^```json\s*|\s*```$", "", response_text.strip())

    return response_text

def generate_description_with_openai(style_number, images, keywords=[]):
    """Generates product descriptions using OpenAI."""
    is_set = "SET" in style_number.upper()
    set_text = "This style is a coordinated clothing set." if is_set else ""
    keyword_list = ", ".join(keywords[:50])

    prompt = f"""
    You are a fashion expert with the combined perspective of a **fashion designer** and a **fashion blogger**. 
    Your role is to analyze and describe the clothing item identified by style number **{style_number}** based on images and extracted text.

    - If the style number contains 'SET', it is a **coordinated clothing set** (e.g., top & bottom, dress & cardigan). 
    - Ensure the **title and description clearly highlight that it is a set**, if applicable.
    - Provide a **detailed yet engaging** description that captures the **silhouette, fit, structure, and key design elements**.
    - Do NOT assume materials or closures unless they are **clearly visible**.
    - Do NOT mention **colors** anywhere (title, description, hashtags, attributes).
    - Seamlessly incorporate these relevant keywords into the description: **{keyword_list}**.
    - Offer **fashion-forward styling suggestions**, including **how to wear the piece, what to pair it with, and suitable occasions or holidays**.

    {set_text}

    **Respond in JSON format like this:**
    {{
        "product_title": "A concise, stylish product title",
        "description": "An engaging, fashion-forward product description with styling insights.",
        "hashtags": ["#fashion", "#trendy", "#style", "#event", "#holiday", "#details"],
        "product_category": "Category name",
        "product_type": "Type name",
        "key_attribute": "One defining visible feature"
    }}
    """

    response = openai.chat.completions.create(
        model="gpt-4-turbo",
        messages=[{"role": "system", "content": "You are a fashion expert."},
                  {"role": "user", "content": [{"type": "text", "text": prompt}] + images}]
    )
    
    raw_text = response.choices[0].message.content

    # 🔍 Debugging: Print raw OpenAI response
    print(f"\n🔍 Debug: OpenAI Raw Response for {style_number}:\n{raw_text}\n")

    cleaned_text = clean_json(raw_text)

    try:
        parsed_data = json.loads(cleaned_text)
    except json.JSONDecodeError as e:
        print(f"❌ ERROR: Failed to parse JSON for {style_number}. Debug: {e}")
        print(f"🔍 Raw JSON Attempt: {cleaned_text}")  # Print what we tried to parse
        return None

    return {
        "Style Number": style_number,
        "Product Title": parsed_data.get("product_title", "N/A"),
        "Product Description": parsed_data.get("description", "N/A"),
        "Tags": ", ".join(parsed_data.get("hashtags", [])),
        "Product Category": parsed_data.get("product_category", "N/A"),
        "Product Type": "Set" if is_set else parsed_data.get("product_type", "N/A"),
        "Option2 Value": parsed_data.get("key_attribute", "N/A")
    }


# ✅ Main Execution
pdf_file = list_files_in_drive(PDF_FOLDER_ID, "application/pdf")

if pdf_file:
    pdf_folder_id = PDF_FOLDER_ID  # ✅ Store the folder ID for later use

    pdf_path = download_file_from_drive(pdf_file["id"], "linesheet.pdf", "pdf")
    extracted_data = extract_text_and_images_from_pdf(pdf_path)
    processed_data = [generate_description_with_openai(entry["style_number"], entry["images"]) for entry in extracted_data]
    
    # ✅ Convert to DataFrame and Save CSV
    df = pd.DataFrame(processed_data)
    csv_file_path = "product_descriptions.csv"
    df.to_csv(csv_file_path, index=False, encoding="utf-8", quoting=1)

    print(f"✅ CSV saved: {csv_file_path}")

    # ✅ Upload CSV to the same Google Drive folder as the PDF
    upload_file_to_drive(csv_file_path, pdf_folder_id)  # Upload it

    print(f"✅ Uploaded CSV to Google Drive in folder: {pdf_folder_id}")

