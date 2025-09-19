import os
from dotenv import load_dotenv

load_dotenv()  

class Config:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "super-secret-key")

    # Use Supabase Transaction Pooler / Shared Pooler URI
    DATABASE_URL = os.getenv("DATABASE_URL")
    SUPERADMIN_LINK = os.environ.get("SUPERADMIN_LINK")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "").strip()
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    IMGBB_API_KEY = os.getenv("IMGBB_API_KEY")