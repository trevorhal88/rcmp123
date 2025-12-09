from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from sqlmodel import SQLModel, Field, Session, create_engine, select
from passlib.context import CryptContext
import stripe
import os
import uuid

# Stripe config
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
stripe.api_key = STRIPE_SECRET_KEY

DATABASE_URL = "sqlite:///./rcmp123.db"
IMAGES_DIR = "images"
os.makedirs(IMAGES_DIR, exist_ok=True)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
engine = create_engine(DATABASE_URL, echo=False)

class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    hashed_password: str

class Listing(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    title: str
    description: str
    price: float
    seller_id: int = Field(foreign_key="user.id")
    image_path: str
    sold: bool = Field(default=False)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session

app = FastAPI(title="RCMP123 Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/images", StaticFiles(directory=IMAGES_DIR), name="images")

@app.on_event("startup")
def on_startup():
    create_db_and_tables()

@app.get("/")
def root():
    return {"message": "backend alive"}

# -------- AUTH --------
@app.post("/register")
def register(
    username: str = Form(...),
    password: str = Form(...),
    session: Session = Depends(get_session),
):
    existing = session.exec(select(User).where(User.username == username)).first()
    if existing:
        raise HTTPException(400, "Username already exists")

    user = User(
        username=username,
        hashed_password=pwd_context.hash(password),
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    return {"id": user.id, "username": user.username}

@app.post("/login")
def login(
    username: str = Form(...),
    password: str = Form(...),
    session: Session = Depends(get_session),
):
    user = session.exec(select(User).where(User.username == username)).first()
    if not user or not pwd_context.verify(password, user.hashed_password):
        raise HTTPException(400, "Invalid Login")

    return {"id": user.id, "username": user.username}

# -------- CREATE LISTING --------
@app.post("/create_listing")
async def create_listing(
    title: str = Form(...),
    description: str = Form(...),
    price: float = Form(...),
    seller_id: int = Form(...),
    image: UploadFile = File(...),
    session: Session = Depends(get_session),
):
    filename = f"{uuid.uuid4()}_{image.filename}"
    path = os.path.join(IMAGES_DIR, filename)

    with open(path, "wb") as f:
        f.write(await image.read())

    listing = Listing(
        title=title,
        description=description,
        price=price,
        seller_id=seller_id,
        image_path=f"/images/{filename}",
    )
    session.add(listing)
    session.commit()
    session.refresh(listing)

    return {"listing_id": listing.id}

# -------- LISTINGS --------
@app.get("/listings")
def get_listings(session: Session = Depends(get_session)):
    listings = session.exec(select(Listing)).all()
    results = []
    for listing in listings:
        seller_username = session.exec(
            select(User.username).where(User.id == listing.seller_id)
        ).first()
        results.append({
            "id": listing.id,
            "title": listing.title,
            "description": listing.description,
            "price": listing.price,
            "image_url": listing.image_path,
            "seller_username": seller_username,
            "sold": listing.sold
        })
    return results

# -------- STRIPE CHECKOUT --------
@app.post("/create_checkout_session")
async def create_checkout_session(
    listing_id: int = Form(...),
    buyer_email: str = Form(...),
    session_db: Session = Depends(get_session)
):
    listing = session_db.exec(select(Listing).where(Listing.id == listing_id)).first()
    if not listing:
        raise HTTPException(404, "Listing not found")
    if listing.sold:
        raise HTTPException(400, "Listing already sold")

    price_cents = int(float(listing.price) * 100)

    try:
        checkout = stripe.checkout.Session.create(
            mode="payment",
            payment_method_types=["card"],
            customer_email=buyer_email,
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "product_data": {
                        "name": listing.title,
                        "images": [],
                    },
                    "unit_amount": price_cents
                },
                "quantity": 1
            }],
            success_url="http://localhost:8000/payment_success?listing_id={}".format(listing.id),
            cancel_url="http://localhost:8000/payment_cancel",
            metadata={
                "listing_id": listing.id
            }
        )
        return {"checkout_url": checkout.url}
    except Exception as e:
        raise HTTPException(500, f"Stripe error: {e}")

@app.post("/stripe_webhook")
async def stripe_webhook(request: Request, session_db: Session = Depends(get_session)):
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    if not webhook_secret:
        raise HTTPException(500, "Missing STRIPE_WEBHOOK_SECRET")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
    except Exception as e:
        raise HTTPException(400, f"Webhook error: {e}")

    if event["type"] == "checkout.session.completed":
        data = event["data"]["object"]
        listing_id = int(data["metadata"]["listing_id"])
        listing = session_db.exec(select(Listing).where(Listing.id == listing_id)).first()
        if listing:
            listing.sold = True
            session_db.add(listing)
            session_db.commit()

    return JSONResponse({"status": "success"})

@app.get("/payment_success")
def payment_success(listing_id: int):
    return {"status": "success", "listing_id": listing_id, "message": "Payment complete. Item marked as sold."}

@app.get("/payment_cancel")
def payment_cancel():
    return {"status": "canceled", "message": "Payment was canceled."}
