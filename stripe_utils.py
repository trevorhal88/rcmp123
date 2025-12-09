import stripe
from config import STRIPE_SECRET_KEY

stripe.api_key = STRIPE_SECRET_KEY

def create_checkout(price_cents: int, item_name: str, listing_id: int, buyer_email: str):
    return stripe.checkout.Session.create(
        mode="payment",
        payment_method_types=["card"],
        customer_email=buyer_email,
        line_items=[{
            "price_data": {
                "currency": "usd",
                "product_data": { "name": item_name },
                "unit_amount": price_cents
            },
            "quantity": 1
        }],
        success_url=f"http://127.0.0.1:8000/payment_success?listing_id={listing_id}",
        cancel_url="http://127.0.0.1:8000/payment_cancel",
        metadata={ "listing_id": listing_id }
    )