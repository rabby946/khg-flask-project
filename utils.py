
import requests, base64
from config import Config

def upload_to_imgbb(file):
    """Upload file to ImageBB and return URL"""
    encoded_image = base64.b64encode(file.read()).decode("utf-8")
    response = requests.post(
        "https://api.imgbb.com/1/upload",
        data={"key": Config.IMGBB_API_KEY, "image": encoded_image}
    )
    if response.status_code == 200:
        return response.json()['data']['url']
    else:
        raise ValueError(f"Image upload failed: {response.text}")
