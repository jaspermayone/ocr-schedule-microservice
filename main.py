# main.py
from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
import pytesseract
from PIL import Image
import io
import cv2
import numpy as np
import uvicorn

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

def process_image(image_bytes):
    # Convert bytes to numpy array
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    
    # Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Apply thresholding
    thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    
    # Convert back to PIL Image
    pil_image = Image.fromarray(thresh)
    
    # Perform OCR
    text = pytesseract.image_to_string(pil_image)
    
    return text

def parse_schedule(text):
    lines = text.split('\n')
    schedule = {}
    current_person = None
    dates = {}
    
    for line in lines:
        # Skip empty lines
        if not line.strip():
            continue
            
        parts = line.split()
        if not parts:
            continue
            
        # If we find the date row (contains multiple '1/' patterns)
        if sum('1/' in part for part in parts) > 1:
            dates = {
                'monday': next((p for p in parts if '1/' in p), ''),
                'tuesday': next((p for p in parts[1:] if '1/' in p), ''),
                'wednesday': next((p for p in parts[2:] if '1/' in p), ''),
                'thursday': next((p for p in parts[3:] if '1/' in p), ''),
                'friday': next((p for p in parts[4:] if '1/' in p), ''),
                'saturday': next((p for p in parts[5:] if '1/' in p), ''),
                'sunday': next((p for p in parts[6:] if '1/' in p), '')
            }
            continue
            
        # Check if this line starts with a name (no numbers or 'OFF')
        if len(parts) >= 1 and not parts[0].replace('-', '').isdigit() and parts[0] != 'OFF' and ':' not in parts[0]:
            # Ignore "CASHIERS" header
            if parts[0] == "CASHIERS":
                continue
            current_person = ' '.join(parts)
            schedule[current_person] = {
                'monday': {'date': dates.get('monday', ''), 'shift': ''},
                'tuesday': {'date': dates.get('tuesday', ''), 'shift': ''},
                'wednesday': {'date': dates.get('wednesday', ''), 'shift': ''},
                'thursday': {'date': dates.get('thursday', ''), 'shift': ''},
                'friday': {'date': dates.get('friday', ''), 'shift': ''},
                'saturday': {'date': dates.get('saturday', ''), 'shift': ''},
                'sunday': {'date': dates.get('sunday', ''), 'shift': ''}
            }
        # If we have shifts data and a current person
        elif current_person and len(parts) >= 7:
            schedule[current_person] = {
                'monday': {'date': dates.get('monday', ''), 'shift': parts[0]},
                'tuesday': {'date': dates.get('tuesday', ''), 'shift': parts[1]},
                'wednesday': {'date': dates.get('wednesday', ''), 'shift': parts[2]},
                'thursday': {'date': dates.get('thursday', ''), 'shift': parts[3]},
                'friday': {'date': dates.get('friday', ''), 'shift': parts[4]},
                'saturday': {'date': dates.get('saturday', ''), 'shift': parts[5]},
                'sunday': {'date': dates.get('sunday', ''), 'shift': parts[6]}
            }
    
    return schedule

@app.post("/ocr")
async def ocr_endpoint(file: UploadFile = File(...)):
    # Read the image file
    image_bytes = await file.read()
    
    # Process the image and get text
    text = process_image(image_bytes)
    
    # Parse the schedule
    schedule = parse_schedule(text)
    
    return {
        "raw_text": text,
        "schedule": schedule
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
