# main.py
from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
import pytesseract
from PIL import Image, ImageEnhance
import io
import re
from datetime import datetime
import numpy as np

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def clean_shift(shift):
    """Clean and standardize shift notation"""
    if not shift:
        return ''
    
    # Convert to uppercase for consistent comparison
    shift = str(shift).strip().upper()
    
    # Return special cases as-is
    if shift in ['OFF', 'GH']:
        return shift
    
    # Handle special cases with words
    if 'CLOSE' in shift or 'OPEN' in shift:
        return shift
        
    # Handle multiple shifts (separated by comma, 'and', or '/')
    shifts = re.split(r'[,/]|\s+AND\s+', shift)
    cleaned_shifts = []
    
    for s in shifts:
        s = s.strip()
        # Extract times using regex
        times = re.findall(r'\d{1,2}(?::\d{2})?(?:-\d{1,2}(?::\d{2})?)?', s)
        if times:
            cleaned_shifts.extend(times)
    
    return ' & '.join(cleaned_shifts) if cleaned_shifts else shift

def process_image(image_bytes):
    # Open image with Pillow
    image = Image.open(io.BytesIO(image_bytes))
    
    # Convert to grayscale
    image = image.convert('L')
    
    # Enhance contrast
    enhancer = ImageEnhance.Contrast(image)
    image = enhancer.enhance(2.0)
    
    # Enhance sharpness
    enhancer = ImageEnhance.Sharpness(image)
    image = enhancer.enhance(2.0)
    
    # Perform OCR with specific config
    custom_config = r'--oem 3 --psm 6'
    text = pytesseract.image_to_string(image, config=custom_config)
    
    return text

def parse_date(date_str):
    """Parse date string expecting MM/DD format"""
    if not date_str:
        return ''
    
    # Remove any non-numeric/slash characters
    date_str = re.sub(r'[^\d/]', '', date_str)
    
    try:
        if '/' in date_str:
            month, day = map(str, date_str.split('/'))
            # Ensure both parts exist and are numbers
            if month.isdigit() and day.isdigit():
                return f"{int(month):02d}/{int(day):02d}"
    except:
        pass
    
    return date_str

def parse_schedule(text):
    lines = text.split('\n')
    schedule = {
        'metadata': {
            'title': '',
            'updated': '',
            'notes': []
        },
        'weeks': []
    }
    
    current_week = {
        'dates': {},
        'employees': {}
    }
    
    current_person = None
    dates_found = False
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Capture metadata
        if 'PARADISE SCHEDULE' in line:
            schedule['metadata']['title'] = 'PARADISE SCHEDULE'
            # Look for updated date
            update_match = re.search(r'Updated\s+(\d{1,2}/\d{1,2})', line)
            if update_match:
                schedule['metadata']['updated'] = update_match.group(1)
            continue
            
        # Capture notes at bottom
        if 'DELI' in line.upper() or 'OPEN TILL' in line.upper():
            schedule['metadata']['notes'].append(line.strip())
            continue
            
        parts = line.split()
        if not parts:
            continue
            
        # If we find a row with multiple dates
        if sum(bool(re.search(r'\d{1,2}/\d{1,2}', part)) for part in parts) > 1:
            dates_found = True
            current_week['dates'] = {
                'monday': parse_date(parts[0]) if len(parts) > 0 else '',
                'tuesday': parse_date(parts[1]) if len(parts) > 1 else '',
                'wednesday': parse_date(parts[2]) if len(parts) > 2 else '',
                'thursday': parse_date(parts[3]) if len(parts) > 3 else '',
                'friday': parse_date(parts[4]) if len(parts) > 4 else '',
                'saturday': parse_date(parts[5]) if len(parts) > 5 else '',
                'sunday': parse_date(parts[6]) if len(parts) > 6 else ''
            }
            continue
            
        # Skip headers
        if parts[0] == "CASHIERS" or "2024" in line:
            continue
            
        # Check for employee name
        if not parts[0].replace('-', '').isdigit() and parts[0] != 'OFF' and ':' not in parts[0]:
            current_person = ' '.join(p for p in parts if not re.match(r'\d{1,2}[-:]\d{1,2}', p))
            if current_person not in current_week['employees']:
                current_week['employees'][current_person] = {
                    'monday': '', 'tuesday': '', 'wednesday': '', 'thursday': '',
                    'friday': '', 'saturday': '', 'sunday': ''
                }
            continue
            
        # Process shifts for current person
        if current_person and len(parts) >= 7:
            shifts = {
                'monday': clean_shift(parts[0]),
                'tuesday': clean_shift(parts[1]),
                'wednesday': clean_shift(parts[2]),
                'thursday': clean_shift(parts[3]),
                'friday': clean_shift(parts[4]),
                'saturday': clean_shift(parts[5]),
                'sunday': clean_shift(parts[6])
            }
            current_week['employees'][current_person].update(shifts)
    
    if dates_found:
        schedule['weeks'].append(current_week)
    
    return schedule

@app.post("/ocr")
async def ocr_endpoint(file: Union[UploadFile, bytes] = File(...)):
    try:
        # If we got raw bytes
        if isinstance(file, bytes):
            image_bytes = file
        # If we got an UploadFile
        else:
            image_bytes = await file.read()
        
        # Process the image and get text
        text = process_image(image_bytes)
        
        # Parse the schedule
        schedule = parse_schedule(text)
        
        return {
            "raw_text": text,
            "schedule": schedule
        }
    except Exception as e:
        return {"error": str(e)}, 422

@app.post("/ocr")
async def ocr_endpoint(file: Union[UploadFile, bytes] = File(...)):
    try:
        # If we got raw bytes
        if isinstance(file, bytes):
            image_bytes = file
        # If we got an UploadFile
        else:
            image_bytes = await file.read()
        
        # Process the image and get text
        text = process_image(image_bytes)
        
        # Parse the schedule
        schedule = parse_schedule(text)
        
        return {
            "raw_text": text,
            "schedule": schedule
        }
    except Exception as e:
        return {"error": str(e)}, 422
        
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
