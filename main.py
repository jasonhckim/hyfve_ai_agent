from modules import ai_description
from modules import google_drive
from modules import utils
import pandas as pd
import yaml



# ✅ Load Configuration from YAML
with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

# ✅ Retrieve Folder IDs from Config
PDF_FOLDER_ID = config["drive_folder_ids"]["pdf"]
DOC_FOLDER_ID = config["drive_folder_ids"]["doc"]
CSV_FOLDER_ID = config["drive_folder_ids"]["csv"]

def get_keywords_from_drive():
    """Fetches keywords from the latest document in Google Drive."""
    doc_file = google_drive.list_files_in_drive(DOC_FOLDER_ID, "text/plain")
    
    if doc_file:
        doc_path = google_drive.download_file_from_drive(doc_file["id"], "keywords.txt")
        return util.extract_keywords_from_doc(doc_path) if doc_path else []
    
    return []

def process_pdf():
    """Extracts data from the latest PDF and generates descriptions with keywords."""
    pdf_file = google_drive.list_files_in_drive(PDF_FOLDER_ID, "application/pdf")
    
    if pdf_file:
        pdf_path = google_drive.download_file_from_drive(pdf_file["id"], "linesheet.pdf")
        extracted_data = google_drive.extract_text_and_images_from_pdf(pdf_path)

        # ✅ Fetch Keywords from Drive
        keywords = get_keywords_from_drive()

        # ✅ Pass keywords to AI description generator
        processed_data = [
            ai_description.generate_description(entry["style_number"], entry["images"], keywords) 
            for entry in extracted_data
        ]

        # ✅ Convert to DataFrame and Save CSV
        df = pd.DataFrame(processed_data)
        csv_file_path = "product_descriptions.csv"
        df.to_csv(csv_file_path, index=False, encoding="utf-8-sig", quoting=1)

        # ✅ Upload CSV to Google Drive
        google_drive.upload_file_to_drive(csv_file_path, CSV_FOLDER_ID)

        print(f"✅ Descriptions generated and uploaded to Google Drive in folder {CSV_FOLDER_ID}")

if __name__ == "__main__":
    process_pdf()
