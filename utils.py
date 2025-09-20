import requests, base64
from config import Config

def upload_to_imgbb(file):
    """Upload file to ImageBB and return URL, or None if failed"""
    try:
        encoded_image = base64.b64encode(file.read()).decode("utf-8")
        response = requests.post(
            "https://api.imgbb.com/1/upload",
            data={"key": Config.IMGBB_API_KEY, "image": encoded_image}
        )
        response.raise_for_status()  # Raise HTTPError for bad responses
        data = response.json()
        if data.get("status_code") == 200:
            return data["data"]["url"]
        else:
            print("ImageBB returned error:", data)
            return None
    except Exception as e:
        print("Image upload failed:", e)
        return None
