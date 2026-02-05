import streamlit as st
import requests
import base64
from PIL import Image
import io

# CONFIG
API_URL = "http://127.0.0.1:8000"

st.set_page_config(page_title="Traffic Intel 🚦", layout="wide")

# Custom CSS
st.markdown("""
    <style>
    .stMetric { background-color: #0E1117; border: 1px solid #333; padding: 10px; border-radius: 5px; }
    </style>
    """, unsafe_allow_html=True)

# AUTH & SESSION SETUP
if 'token' not in st.session_state: st.session_state.token = None
if 'username' not in st.session_state: st.session_state.username = None

# --- LOGIN / REGISTER PAGE ---
def login_page():
    st.title("🛡️ Secure Access Required")
    
    # Create two tabs: one for existing officers, one for new recruits
    tab1, tab2 = st.tabs(["🔑 Login", "📝 Register"])

    # === TAB 1: LOGIN ===
    with tab1:
        username = st.text_input("Username", key="login_user")
        password = st.text_input("Password", type="password", key="login_pass")
        if st.button("Login", type="primary"):
            try:
                # Send credentials to FastAPI
                res = requests.post(f"{API_URL}/login", json={"username": username, "password": password})
                
                if res.status_code == 200:
                    # Success! Save the token and reload the app
                    st.session_state.token = res.json()['access_token']
                    st.session_state.username = username
                    st.success("Access Granted. Loading Dashboard...")
                    st.rerun()
                else:
                    st.error("❌ Invalid Credentials. Access Denied.")
            except Exception as e:
                st.error(f"⚠️ System Offline: {e}")

    # === TAB 2: REGISTER ===
    with tab2:
        st.subheader("New Officer Registration")
        new_user = st.text_input("New Username", key="reg_user")
        new_pass = st.text_input("New Password", type="password", key="reg_pass")
        
        if st.button("Register Account"):
            if not new_user or not new_pass:
                st.warning("Please fill in both fields.")
            else:
                try:
                    # Send new user data to FastAPI
                    res = requests.post(f"{API_URL}/register", json={"username": new_user, "password": new_pass})
                    
                    if res.status_code == 200:
                        st.balloons() # 🎉
                        st.success("✅ Registration Successful! Please switch to the Login tab.")
                    else:
                        st.error(f"Registration Failed: {res.text}")
                except Exception as e:
                    st.error(f"⚠️ Connection Failed: {e}")
                    
# --- MAIN DASHBOARD ---
def main_dashboard():
    # SIDEBAR CONTROLS
    with st.sidebar:
        st.title("🎛️ Control Panel")
        st.write(f"Officer: **{st.session_state.username}**")
        
        # 🎚️ CONFIDENCE SLIDER (The requested feature)
        confidence = st.slider("AI Confidence Threshold", 0.0, 1.0, 0.25, 0.05, help="Higher = Stricter, Lower = More detections (but maybe wrong ones)")
        
        st.divider()
        st.info(f"System Status: ONLINE ✅")
        if st.button("Logout"):
            st.session_state.token = None
            st.rerun()

    st.title("🚦 Traffic Intelligence Hub")
    
    headers = {"Authorization": f"Bearer {st.session_state.token}"}
    tab_img, tab_vid, tab_live = st.tabs(["📸 Photo", "🎥 Video", "📡 Live Feed"])

    # === TAB 1: PHOTO ===
    with tab_img:
        uploaded_file = st.file_uploader("Upload Image", type=['jpg', 'png'])
        if uploaded_file and st.button("Analyze Photo"):
            with st.spinner("Detecting objects..."):
                # OPTION 2 FIX: Explicitly setting MIME type
                files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
                params = {"conf": confidence} # Pass slider value
                
                try:
                    res = requests.post(f"{API_URL}/predict/image", files=files, headers=headers, params=params)
                    if res.status_code == 200:
                        data = res.json()
                        
                        # Decode the Base64 image sent by backend
                        img_data = base64.b64decode(data['annotated_image'])
                        annotated_img = Image.open(io.BytesIO(img_data))
                        
                        col1, col2 = st.columns([2, 1])
                        with col1:
                            st.image(annotated_img, caption="AI Vision Overlay", use_container_width=True)
                        with col2:
                            st.metric("Total Vehicles", data['total_vehicles'])
                            st.json(data['breakdown'])
                    else:
                        st.error(f"Error: {res.text}")
                except Exception as e:
                    st.error(f"Connection Failed: {e}")

    # === TAB 2: VIDEO ===
    with tab_vid:
        video_file = st.file_uploader("Upload Video", type=['mp4'])
        if video_file and st.button("Process Video Overlay"):
            st.warning("⏳ Processing video frames... This might take 10-20 seconds.")
            with st.spinner("AI is drawing bounding boxes..."):
                files = {"file": ("video.mp4", video_file.getvalue(), "video/mp4")}
                params = {"conf": confidence}
                
                try:
                    res = requests.post(f"{API_URL}/predict/video", files=files, headers=headers, params=params)
                    if res.status_code == 200:
                        st.success("Processing Complete!")
                        st.video(res.content) # Streamlit can play the bytes directly
                    else:
                        st.error(f"Server Error: {res.text}")
                except Exception as e:
                    st.error(f"Failed: {e}")

    # === TAB 3: LIVE FEED ===
    with tab_live:
        st.subheader("Field Camera Feed")
        camera_img = st.camera_input("Capture Frame")
        
        if camera_img:
            # OPTION 2 FIX APPLIED HERE TOO
            files = {"file": ("live_capture.jpg", camera_img.getvalue(), "image/jpeg")}
            params = {"conf": confidence}
            
            try:
                res = requests.post(f"{API_URL}/predict/image", files=files, headers=headers, params=params)
                if res.status_code == 200:
                    data = res.json()
                    
                    # Display the Annotated Image
                    img_data = base64.b64decode(data['annotated_image'])
                    annotated_img = Image.open(io.BytesIO(img_data))
                    
                    st.image(annotated_img, caption="Live Analysis", use_container_width=True)
                    st.metric("Count", data['total_vehicles'], delta=data['status'])
                else:
                    st.error(f"Server rejected image: {res.text}")
            except Exception as e:
                st.error(f"System Offline: {e}")

if st.session_state.token:
    main_dashboard()
else:
    login_page()