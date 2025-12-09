import base64
import requests

API_BASE = "http://127.0.0.1:8000"

def create_listing_via_gpt(title, description, price, seller_id, image_base64: str):
    image_bytes = base64.b64decode(image_base64)

    files = {
        "image": ("photo.jpg", image_bytes, "image/jpeg")
    }
    data = {
        "title": title,
        "description": description,
        "price": str(price),
        "seller_id": str(seller_id),
    }

    r = requests.post(f"{API_BASE}/create_listing", data=data, files=files)
    r.raise_for_status()
    return r.json()
