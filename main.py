import shutil
import tempfile
import cv2
import os
import base64
from fastapi import FastAPI, HTTPException, Depends, File, UploadFile, Query
from fastapi.responses import JSONResponse, FileResponse
from ultralytics import YOLO
from PIL import Image
import io
import numpy as np
from collections import Counter
from auth import verify_token, UserAuth, TokenResponse, register_new_user, authenticate_user, create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES
from datetime import timedelta

app = FastAPI(title="Traffic Intelligence API 🚦")

# Load Model
MODEL_PATH = 'best.pt'
if not os.path.exists(MODEL_PATH):
    raise FileNotFoundError(f"⚠️ Model file not found at {MODEL_PATH}")
model = YOLO(MODEL_PATH)

# ---------------------------------------------------------
# 📸 1. IMAGE PREDICTION (Returns Stats + Annotated Image)
# ---------------------------------------------------------
@app.post('/predict/image')
async def predict_image(
    file: UploadFile = File(...), 
    conf: float = Query(0.25, ge=0.0, le=1.0), # <--- Receive Confidence Slider Value
    username: str = Depends(verify_token)
):
    try:
        # Read Image
        contents = await file.read()
        image = Image.open(io.BytesIO(contents))

        # Run YOLO with the user's confidence level
        results = model.predict(image, conf=conf)
        result = results[0]
        
        # A. DRAW BOXES (The "Info Box" Overlay)
        # plot() returns a NumPy array (BGR format)
        annotated_array = result.plot() 
        # Convert BGR (OpenCV) to RGB (PIL)
        annotated_image = Image.fromarray(cv2.cvtColor(annotated_array, cv2.COLOR_BGR2RGB))

        # Encode image to Base64 string to send back to Streamlit
        buf = io.BytesIO()
        annotated_image.save(buf, format="JPEG")
        img_str = base64.b64encode(buf.getvalue()).decode("utf-8")

        # B. COUNT VEHICLES
        names = result.names
        counts = Counter([names[int(c)] for c in result.boxes.cls.cpu().numpy()])
        total = sum(counts.values())

        return {
            "total_vehicles": total,
            "breakdown": dict(counts),
            "status": "Congested 🚨" if total > 15 else "Clear ✅",
            "annotated_image": img_str # <--- Sending the drawing back!
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ---------------------------------------------------------
# 🎥 2. VIDEO PREDICTION (Returns Processed Video File)
# ---------------------------------------------------------
@app.post('/predict/video')
async def predict_video(
    file: UploadFile = File(...), 
    conf: float = Query(0.25),
    username: str = Depends(verify_token)
):
    if "video" not in file.content_type:
        raise HTTPException(status_code=400, detail="File must be a video.")

    # Create Temp Input and Output Files
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as input_vid:
        shutil.copyfileobj(file.file, input_vid)
        input_path = input_vid.name
    
    output_path = input_path.replace(".mp4", "_out.mp4")

    try:
        # Open Video
        cap = cv2.VideoCapture(input_path)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        
        # Initialize Video Writer (mp4v codec is widely supported)
        # NEW (Good for browsers - H.264)
        fourcc = cv2.VideoWriter_fourcc(*'avc1') 
        out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

        frame_count = 0
        
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            
            # Process every frame (Or skip frames if Render is too slow)
            # plot() draws the boxes directly on the frame
            results = model.predict(frame, conf=conf, verbose=False)
            annotated_frame = results[0].plot()
            
            out.write(annotated_frame)
            frame_count += 1
            
            # Limit for Free Tier Safety (Stop after 10 seconds / ~300 frames)
            if frame_count > 300: 
                break 

        cap.release()
        out.release()
        
        # Return the processed video file directly
        return FileResponse(output_path, media_type="video/mp4", filename="traffic_analysis.mp4")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Cleanup input (we keep output for the response, FastAPI cleans temp files usually)
        if os.path.exists(input_path):
            os.remove(input_path)

# ---------------------------------------------------------
# 🔐 AUTH ENDPOINTS (Kept exactly the same)
# ---------------------------------------------------------

@app.post('/register', response_model=TokenResponse)
def register(user: UserAuth):
    register_new_user(user)
    access_token = create_access_token(
        data={"sub": user.username}, 
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return {'access_token': access_token, 'token_type': 'Bearer', 'expires_in': ACCESS_TOKEN_EXPIRE_MINUTES * 60}

@app.post('/login', response_model=TokenResponse)
def login(user: UserAuth):
    authenticated_user = authenticate_user(user)
    if not authenticated_user:
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    
    access_token = create_access_token(
        data={'sub': user.username}, 
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return {'access_token': access_token, 'token_type': 'Bearer', 'expires_in': ACCESS_TOKEN_EXPIRE_MINUTES * 60}