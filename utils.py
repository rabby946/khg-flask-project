import cloudinary
import cloudinary.uploader
from config import Config

# Configure Cloudinary
cloudinary.config(
    cloud_name=Config.CLOUD_NAME,
    api_key=Config.CLOUD_API_KEY,
    api_secret=Config.CLOUD_API_SECRET
)

def upload_to_imgbb(file):
    """
    Upload a file object to Cloudinary and return its secure URL.
    """
    result = cloudinary.uploader.upload(file)
    return result['secure_url']
