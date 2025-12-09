def generate_listing(raw_text: str):
    return {
        "title": raw_text[:40] + " RC Car",
        "description": raw_text,
        "suggested_price": 120
    }