from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlmodel import SQLModel, Field, Session, create_engine, select
from passlib.context import CryptContext
import stripe
import os
import uuid

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
    allow_headers=["*"]
)

app.mount("/images", StaticFiles(directory=IMAGES_DIR), name="images")

@app.on_event("startup")
def on_startup():
    create_db_and_tables()

@app.get("/")
def root():
    return {"message": "backend alive"}

@app.post("/register")
def register(username: str = Form(...), password: str = Form(...), session: Session = Depends(get_session)):
    existing = session.exec(select(User).where(User.username == username)).first()
    if existing:
        raise HTTPException(400, "Username exists")

    user = User(
        username=username,
        hashed_password=pwd_context.hash(password)
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    return {"id": user.id, "username": user.username}

@app.post("/create_listing")
async def create_listing(
    title: str = Form(...),
    description: str = Form(...),
    price: float = Form(...),
    seller_id: int = Form(...),
    image: UploadFile = File(...),
    session: Session = Depends(get_session)
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
        image_path=f"/images/{filename}"
    )
    session.add(listing)
    session.commit()
    session.refresh(listing)

    return {"listing_id": listing.id}