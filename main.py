from fastapi import FastAPI, HTTPException, Depends, status

from pydantic import BaseModel, field_validator
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm


import bcrypt
import jwt

import os
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import sessionmaker, declarative_base, Session

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, "auth_app.db")
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class User(Base):
    """
    Model użytkownika w bazie danych.
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    # zahashowane hasło (bcrypt)
    password_hash = Column(String, nullable=False)
    # role przechowywane jako ciąg znaków, np. "ROLE_ADMIN,ROLE_USER"
    roles = Column(String, nullable=False)


Base.metadata.create_all(bind=engine)


def get_db():
    """
    Dependency FastAPI – zwraca sesję bazy danych.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_default_admin():
    """
    Tworzy domyślnego admina (admin / admin123) z rolą ROLE_ADMIN,
    jeśli nie istnieje w bazie.
    """
    db: Session = SessionLocal()
    try:
        admin = db.query(User).filter(User.username == "admin").first()
        if not admin:
            hashed_pw = bcrypt.hashpw(b"admin123", bcrypt.gensalt())
            admin_user = User(
                username="admin",
                password_hash=hashed_pw.decode("utf-8"),
                roles="ROLE_ADMIN"
            )
            db.add(admin_user)
            db.commit()
    finally:
        db.close()


create_default_admin()

# -----------------------------
# Konfiguracja JWT i FastAPI
# -----------------------------

app = FastAPI()

SECRET_KEY = "super_secret_key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 1

# Używamy schematu OAuth2 z Bearer tokenem
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")


# -----------------------------
# Schemy Pydantic
# -----------------------------

class LoginData(BaseModel):
    username: str
    password: str


class UserCreate(BaseModel):
    username: str
    password: str
    roles: List[str] = []  # np. ["ROLE_USER"], ["ROLE_ADMIN"]


class UserOut(BaseModel):
    id: int
    username: str
    roles: List[str]

    @field_validator("roles", mode="before")
    @classmethod
    def split_roles(cls, v):
        # jeśli z bazy przychodzi string "ROLE_ADMIN,ROLE_USER"
        if isinstance(v, str):
            return [r for r in v.split(",") if r]
        # jeśli to już lista, zostaw jak jest
        return v

    class Config:
        from_attributes = True  # zamiast orm_mode w Pydantic v2


# -----------------------------
# Funkcje pomocnicze JWT
# -----------------------------

def create_access_token(*, username: str, roles: List[str]) -> str:
    now = datetime.utcnow()
    payload = {
        "sub": username,
        "roles": roles,
        "iat": now,
        "exp": now + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS),
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return token


def get_current_user(token: str = Depends(oauth2_scheme)):
    """
    Dependency: pobiera i weryfikuje token z nagłówka Authorization.
    Zwraca payload JWT (słownik).
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: Optional[str] = payload.get("sub")
        if username is None:
            raise credentials_exception
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise credentials_exception
    return payload


def require_admin(current_user=Depends(get_current_user)):
    """
    Dependency: wymaga aby zalogowany użytkownik miał rolę ROLE_ADMIN.
    """
    roles = current_user.get("roles", [])
    if "ROLE_ADMIN" not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return current_user


# -----------------------------
# Endpointy
# -----------------------------

@app.post("/login")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    username = form_data.username
    password_bytes = form_data.password.encode("utf-8")

    user: User | None = db.query(User).filter(User.username == username).first()
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    hashed_pw = user.password_hash.encode("utf-8")

    if not bcrypt.checkpw(password_bytes, hashed_pw):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    roles = user.roles.split(",") if user.roles else []
    token = create_access_token(username=username, roles=roles)
    return {"access_token": token, "token_type": "bearer"}


@app.post("/users", response_model=UserOut)
def create_user(
    new_user: UserCreate,
    db: Session = Depends(get_db),
    current_admin=Depends(require_admin),
):
    """
    (4) Endpoint POST /users – dodawanie nowego użytkownika do bazy.
    Dostęp tylko dla ROLE_ADMIN.
    """
    existing = db.query(User).filter(User.username == new_user.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already taken")

    hashed_pw = bcrypt.hashpw(new_user.password.encode("utf-8"), bcrypt.gensalt())
    roles_str = ",".join(new_user.roles) if new_user.roles else ""

    user_obj = User(
        username=new_user.username,
        password_hash=hashed_pw.decode("utf-8"),
        roles=roles_str,
    )
    db.add(user_obj)
    db.commit()
    db.refresh(user_obj)
    return user_obj


@app.get("/user_details")
def user_details(current_user=Depends(get_current_user)):
    """
    (7) Endpoint /user_details – zwraca dane użytkownika z payloadu JWT.
    """
    return current_user
