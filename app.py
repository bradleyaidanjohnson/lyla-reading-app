import uuid
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import streamlit as st
import random
import json
import time
import os
from googleapiclient.http import MediaIoBaseDownload
import io

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import streamlit as st

SCOPES = ["https://www.googleapis.com/auth/drive.file"]

def get_drive_service():
    gd = st.secrets["google_drive"]

    creds = Credentials(
        None,
        refresh_token=gd["refresh_token"],
        client_id=gd["client_id"],
        client_secret=gd["client_secret"],
        token_uri=gd["token_uri"],
        scopes=SCOPES
    )

    service = build("drive", "v3", credentials=creds)
    return service

def get_drive_folder_id():
    return st.secrets["google_drive"]["drive_folder_id"]


def get_drive_image_url(file_id):
    return f"https://drive.google.com/uc?export=view&id={file_id}"


WORDS_FILE = "words.json"
IMAGES_DIR = "images"

# Ensure local images dir exists
os.makedirs(IMAGES_DIR, exist_ok=True)

def fetch_image_if_needed(file_id, filename):
    """Downloads image from Drive if it's missing locally."""
    local_path = f"{IMAGES_DIR}/{filename}"

    if os.path.exists(local_path):
        return local_path  # Already cached locally

    try:
        service = get_drive_service()
        request = service.files().get_media(fileId=file_id)
        fh = io.FileIO(local_path, "wb")
        downloader = MediaIoBaseDownload(fh, request)

        done = False
        while not done:
            status, done = downloader.next_chunk()

        return local_path

    except Exception as e:
        st.error(f"⚠ Could not download image: {e}")
        return None

# ---------- Load/Save Word List ----------
def load_words():
    if not os.path.exists(WORDS_FILE):
        return []
    with open(WORDS_FILE, "r") as f:
        return json.load(f)

def save_words(words):
    with open(WORDS_FILE, "w") as f:
        json.dump(words, f, indent=4)

words = load_words()

def display_word(word, font_size=120):
    return f"""
    <h1 class='comic-word' style='font-size:{font_size}px;'>{word}</h1>
    """



# ---------- Sidebar Navigation ----------
page = st.sidebar.selectbox("Menu", ["Play", "Word Library", "Settings"])

st.title("📖 Reading Trainer")

# ---------- Settings Page ----------
if page == "Settings":
    st.subheader("Timing Controls")
    word_time = st.number_input("Time showing word only (seconds)", 1, 20, 3)
    reveal_time = st.number_input("Time showing word + picture (seconds)", 1, 10, 3)

    # Save values in session_state
    st.session_state["word_time"] = word_time
    st.session_state["reveal_time"] = reveal_time

    st.success("Settings saved automatically!")

# ---------- Word Library Page ----------
elif page == "Word Library":
    st.subheader("Word List")

    # Display and edit words
    for idx, entry in enumerate(words):
        cols = st.columns([2,1,1,1])
        cols[0].write(entry["word"])
        
        active_state = cols[1].checkbox("Active", value=entry.get("active", True), key=f"active_{idx}")
        
        # If checkbox changed → update memory + save immediately
        if active_state != entry.get("active"):
            words[idx]["active"] = active_state
            save_words(words)

        # Image preview (Drive cached)
        if entry.get("drive_id"):
            img_path = fetch_image_if_needed(entry["drive_id"], entry["image"])
            if img_path:
                cols[2].image(img_path, width=70)
        else:
            cols[2].write("no image")

        if cols[3].button("Delete", key=f"delete_{idx}"):
            words.pop(idx)
            save_words(words)
            st.rerun()


    st.markdown("---")
    
    # Add new word
    st.subheader("Add New Word")
    new_word = st.text_input("Word")
    img_file = st.file_uploader("Upload image")

    if img_file is not None and st.button("Add Word"):
      ext = img_file.name.split(".")[-1]
      file_id = str(uuid.uuid4())
      new_filename = f"{new_word.lower()}_{file_id}.{ext}"

      # Save temporarily
      # Create a temp folder locally if it doesn't exist
      TEMP_DIR = "temp"
      os.makedirs(TEMP_DIR, exist_ok=True)

      temp_path = os.path.join(TEMP_DIR, new_filename)
      with open(temp_path, "wb") as f:
          f.write(img_file.getbuffer())


      # Upload to Drive
      service = get_drive_service()
      file_metadata = {"name": new_filename, "parents": [get_drive_folder_id()]}
      media = MediaFileUpload(temp_path, resumable=True)
      uploaded = service.files().create(body=file_metadata, media_body=media, fields="id").execute()

      # Store reference
      words.append({
          "word": new_word,
          "image": new_filename,
          "drive_id": uploaded["id"],
          "active": True  # IMPORTANT
      })

      save_words(words)

      st.success(f"Added {new_word} and uploaded to Drive")

      st.rerun()

    else:
        st.error("Word + image required")

# ---------- Play Mode Page ----------
elif page == "Play":
    st.subheader("Reading Session")

    active_words = [w for w in words if w["active"]]

    # ----- STATE INIT -----
    if "running" not in st.session_state:
        st.session_state.running = False
    if "current_word" not in st.session_state:
        st.session_state.current_word = None
    if "mode" not in st.session_state:
        st.session_state.mode = "word_only"   # word_only → word+image

    # ----- Start / Stop Buttons -----
    start = st.button("▶ Start Session", disabled=st.session_state.running)
    stop = st.button("⏹ Stop Session", disabled=not st.session_state.running)

    if start:
        if not active_words:
            st.warning("No active words selected!")
        else:
            st.session_state.running = True
            st.session_state.mode = "word_only"
            st.session_state.current_word = random.choice(active_words)
            st.rerun()

    if stop:
        st.session_state.running = False
        st.session_state.mode = "word_only"
        st.rerun()

    # ----- LOOPING DISPLAY -----
    if st.session_state.running:

        # Create a dedicated placeholder so we can clear the image cleanly
        word_box = st.empty()
        image_box = st.empty()

        word = st.session_state.current_word["word"]
        img_filename = st.session_state.current_word["image"]
        img_id = st.session_state.current_word.get("drive_id")
        img_path = fetch_image_if_needed(img_id, img_filename) if img_id else None


        # 1. WORD ONLY (no image visible)
        if st.session_state.mode == "word_only":
            word_box.markdown(display_word(word, 120), unsafe_allow_html=True)
            image_box.empty()  # <<< This force-removes previous picture
            time.sleep(st.session_state.get("word_time", 3))
            st.session_state.mode = "word_img"
            st.rerun()

        # 2. WORD + IMAGE
        elif st.session_state.mode == "word_img":
            word_box.markdown(display_word(word, 120), unsafe_allow_html=True)
            if img_path:
                image_box.image(img_path, use_container_width=True)
            time.sleep(st.session_state.get("reveal_time", 3))

            # Choose next word and restart loop
            active_words = [w for w in words if w["active"]]
            st.session_state.current_word = random.choice(active_words)
            st.session_state.mode = "word_only"
            st.rerun()
