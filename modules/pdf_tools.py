import fitz  # PyMuPDF
import re
import base64
import io
from PIL import Image
import yaml

# Load config
with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

STYLE_REGEX = config["regex_patterns"]["style_number"]

def extract_style_number(text):
    """Extracts style numbers from text using regex."""
    matches = re.findall(STYLE_REGEX, text)
    return matches[0][0] if matches else "Unknown"

def extract_text_and_images(pdf_path):
    """Extracts text and images from a PDF."""
    doc = fitz.open(pdf_path)
    extracted_data = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text")
        style_number = extract_style_number(text)
        
        images = []
        for img in page.get_images(full=True):
            xref = img[0]
            base_image = doc.extract_image(xref)
            image = Image.open(io.BytesIO(base_image["image"]))
            img_io = io.BytesIO()
            image.save(img_io, format="JPEG")
            img_base64 = base64.b64encode(img_io.getvalue()).decode("utf-8")
            images.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_base64}"}})
        
        extracted_data.append({"page": page_num + 1, "style_number": style_number, "text": text.strip(), "images": images})
    
    return extracted_data
