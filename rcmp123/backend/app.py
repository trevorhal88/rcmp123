from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlmodel import SQLModel, Field, Session, create_engine, select
from passlib.context import CryptContext
from pydantic import BaseModel
import os
import uuid
import stripe

# --------------------
# CONFIG
# --------------------
DATABASE_URL = "sqlite:///./rcmp123.db"
IMAGES_DIR = "images"

os.makedirs(IMAGES_DIR, exist_ok=True)

engine = create_engine(DATABASE_URL, echo=False)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Stripe
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
PLATFORM_FEE_CENTS = 123  # $1.23 fee for your platform
FRONTEND_URL = "http://127.0.0.1:5500/frontend"  # update if you host elsewhere

if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY
else:
    print("WARNING: STRIPE_SECRET_KEY not set. Stripe checkout will fail until you set it.")


# --------------------
# DB MODELS
# --------------------
class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    hashed_password: str
    stripe_account_id: str | None = None  # seller's Stripe Connect account ID


class Listing(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    title: str
    description: str
    price: float  # dollars
    seller_id: int = Field(foreign_key="user.id")
    image_path: str
    sold: bool = Field(default=False)


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session


# --------------------
# SCHEMAS
# --------------------
class ListingPublic(BaseModel):
    id: int
    title: str
    description: str
    price: float
    seller_username: str
    image_url: str
    sold: bool

    class Config:
        orm_mode = True


class CheckoutRequest(BaseModel):
    listing_id: int
    buyer_email: str


# --------------------
# APP SETUP
# --------------------
app = FastAPI(title="RCMP123 Marketplace")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # loosen for dev; restrict later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/images", StaticFiles(directory=IMAGES_DIR), name="images")


@app.on_event("startup")
def on_startup():
    create_db_and_tables()


# --------------------
# AUTH HELPERS
# --------------------
def hash_pw(password: str) -> str:
    return pwd_context.hash(password)


def verify_pw(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)


# --------------------
# ROUTES
# --------------------
@app.get("/")
def root():
    return {"message": "RCMP123 full backend running"}


# REGISTER USER
@app.post("/register")
def register(
    username: str = Form(...),
    password: str = Form(...),
    stripe_account_id: str | None = Form(None),
    session: Session = Depends(get_session),
):
    existing = session.exec(select(User).where(User.username == username)).first()
    if existing:
        raise HTTPException(400, "Username already exists")

    user = User(
        username=username,
        hashed_password=hash_pw(password),
        stripe_account_id=stripe_account_id,
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    return {
        "id": user.id,
        "username": user.username,
        "stripe_account_id": user.stripe_account_id,
    }


# LOGIN
@app.post("/login")
def login(
    username: str = Form(...),
    password: str = Form(...),
    session: Session = Depends(get_session),
):
    user = session.exec(select(User).where(User.username == username)).first()
    if not user or not verify_pw(password, user.hashed_password):
        raise HTTPException(401, "Invalid username or password")

    return {
        "id": user.id,
        "username": user.username,
        "stripe_account_id": user.stripe_account_id,
    }


# CREATE LISTING
@app.post("/create_listing")
async def create_listing(
    title: str = Form(...),
    description: str = Form(...),
    price: float = Form(...),
    seller_id: int = Form(...),
    image: UploadFile = File(...),
    session: Session = Depends(get_session),
):
    seller = session.get(User, seller_id)
    if not seller:
        raise HTTPException(400, "Invalid seller_id")

    filename = f"{uuid.uuid4()}_{image.filename}"
    image_path_disk = os.path.join(IMAGES_DIR, filename)

    with open(image_path_disk, "wb") as f:
        f.write(await image.read())

    listing = Listing(
        title=title,
        description=description,
        price=price,
        seller_id=seller.id,
        image_path=f"/images/{filename}",
    )
    session.add(listing)
    session.commit()
    session.refresh(listing)

    return {"status": "ok", "listing_id": listing.id}


# GET ALL LISTINGS
@app.get("/listings", response_model=list[ListingPublic])
def get_listings(session: Session = Depends(get_session)):
    listings = session.exec(select(Listing)).all()
    result: list[ListingPublic] = []
    for l in listings:
        seller = session.get(User, l.seller_id)
        result.append(
            ListingPublic(
                id=l.id,
                title=l.title,
                description=l.description,
                price=l.price,
                seller_username=seller.username if seller else "Unknown",
                image_url=l.image_path,
                sold=l.sold,
            )
        )
    return result


# STRIPE CHECKOUT
@app.post("/create_checkout_session")
def create_checkout_session(
    data: CheckoutRequest, session: Session = Depends(get_session)
):
    if not STRIPE_SECRET_KEY:
        raise HTTPException(500, "Stripe not configured (missing STRIPE_SECRET_KEY)")

    listing = session.get(Listing, data.listing_id)
    if not listing:
        raise HTTPException(404, "Listing not found")

    if listing.sold:
        raise HTTPException(400, "Listing already sold")

    seller = session.get(User, listing.seller_id)
    if not seller or not seller.stripe_account_id:
        raise HTTPException(400, "Seller not connected to Stripe")

    amount_cents = int(round(listing.price * 100))

    try:
        checkout_session = stripe.checkout.Session.create(
            mode="payment",
            customer_email=data.buyer_email,
            line_items=[
                {
                    "price_data": {
                        "currency": "usd",
                        "product_data": {
                            "name": listing.title,
                            "description": listing.description,
                        },
                        "unit_amount": amount_cents,
                    },
                    "quantity": 1,
                }
            ],
            payment_intent_data={
                "application_fee_amount": PLATFORM_FEE_CENTS,  # your $1.23
                "transfer_data": {
                    "destination": seller.stripe_account_id  # rest to seller
                },
            },
            success_url=f"{FRONTEND_URL}/success.html?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{FRONTEND_URL}/cancel.html",
        )

        return {"checkout_url": checkout_session.url}
    except Exception as e:
        raise HTTPException(500, f"Stripe error: {e}")
