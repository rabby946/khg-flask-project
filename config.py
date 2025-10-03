import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "super-secret-key")
    DATABASE_URL = os.getenv("DATABASE_URL")
    SUPERADMIN_LINK = os.getenv("SUPERADMIN_LINK")
    SUPERADMIN_PASSWORD = os.getenv("SUPERADMIN_PASSWORD", "").strip()
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # --- Brevo API configuration ---
    BREVO_API_KEY = os.getenv("BREVO_API_KEY")
    BREVO_SENDER_EMAIL = os.getenv("BREVO_SENDER_EMAIL", "korjehasanahgroup@gmail.com")
    BREVO_SENDER_NAME = os.getenv("BREVO_SENDER_NAME", "Korje Hasanah Group")

    # Cloudinary credentials
    CLOUD_NAME = os.getenv("CLOUD_NAME")
    CLOUD_API_KEY = os.getenv("CLOUD_API_KEY")
    CLOUD_API_SECRET = os.getenv("CLOUD_API_SECRET")
