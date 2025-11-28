from fastapi import FastAPI, Depends
from fastapi.responses import Response
from pydantic import BaseModel
from typing import List
import os
import csv

from sqlalchemy import create_engine, Column, Integer, String, Float
from sqlalchemy.orm import sessionmaker, declarative_base, Session

# ---------- KONFIGURACJA BAZY ----------

BASE_DIR = os.path.dirname(__file__) # katalog, w którym jest server.py __file__ oznacza bieżący plik
DB_PATH = os.path.join(BASE_DIR, "database", "movies2.db")  # tutaj tworzy się plik DB
DATABASE_URL = f"sqlite:///{DB_PATH}" # SQLite URL

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # potrzebne przy SQLite + FastAPI
) # silnik bazy danych SQLAlchemy 
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine) # fabryka sesji DB

Base = declarative_base() # klasa bazowa dla modeli ORM


class MovieDB(Base):
    __tablename__ = "movies"

    id = Column(Integer, primary_key=True, index=True)  # sztuczne ID
    movieId = Column(Integer, index=True)
    title = Column(String, nullable=False)
    genres = Column(String, nullable=False)


class RatingDB(Base):
    __tablename__ = "ratings"

    id = Column(Integer, primary_key=True, index=True)
    userId = Column(Integer, index=True)
    movieId = Column(Integer, index=True)
    rating = Column(Float, nullable=False)
    timestamp = Column(Integer, nullable=False)

class linksDB(Base):
    __tablename__ = "links"

    id = Column(Integer, primary_key=True, index=True)
    movieId = Column(Integer, index=True)
    imdbId = Column(Integer, nullable=True)
    tmdbId = Column(Integer, nullable=True)

class TagsDB(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, index=True)
    userId = Column(Integer, index=True)
    movieId = Column(Integer, index=True)
    tag = Column(String, nullable=False)
    timestamp = Column(Integer, nullable=False)


# ---------- Pydantic modele (to co wychodzi na zewnątrz) ----------

class Movie(BaseModel):
    movieId: int
    title: str
    genres: str

    class Config:
        orm_mode = True  # pozwala FastAPI czytać dane z ORM (SQLAlchemy)


class Rating(BaseModel):
    userId: int
    movieId: int
    rating: float
    timestamp: int

    class Config:
        orm_mode = True

class links(BaseModel):
    movieId: int
    imdbId: int
    tmdbId: int

    class Config:
        orm_mode = True

class Tags(BaseModel):
    userId: int
    movieId: int
    tag: str
    timestamp: int

    class Config:
        orm_mode = True


# ---------- FASTAPI ----------

app = FastAPI()


@app.get("/")
def read_root():
    return {"hello": "world"}


# Dependency – sesja DB dla endpointów
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------- INICJALIZACJA BAZY I ŁADOWANIE CSV ----------

def init_db():
    """
    Tworzy tabele, jeśli nie istnieją,
    i ładuje dane z CSV tylko wtedy, gdy tabele są puste.
    """
    Base.metadata.create_all(bind=engine)

    db: Session = SessionLocal()

    # --- Ładowanie filmów ---
    if db.query(MovieDB).first() is None:
        csv_path = os.path.join(BASE_DIR, "database", "movies.csv")
        with open(csv_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                movie = MovieDB(
                    movieId=int(row["movieId"]),
                    title=row["title"],
                    genres=row["genres"],
                )
                db.add(movie)
        db.commit()

    # --- Ładowanie ocen ---
    if db.query(RatingDB).first() is None:
        csv_path = os.path.join(BASE_DIR, "database", "ratings.csv")
        with open(csv_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rating = RatingDB(
                    userId=int(row["userId"]),
                    movieId=int(row["movieId"]),
                    rating=float(row["rating"]),
                    timestamp=int(row["timestamp"]),
                )
                db.add(rating)
        db.commit()

    if db.query(linksDB).first() is None:
        csv_path = os.path.join(BASE_DIR, "database", "links.csv")
        with open(csv_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                link = linksDB(
                    movieId=int(row["movieId"]),
                    imdbId=int(row["imdbId"]),
                    tmdbId=int(row['tmdbId']) if row['tmdbId'].isdigit() else None,
                )
                db.add(link)
        db.commit()

    if db.query(TagsDB).first() is None:
        csv_path = os.path.join(BASE_DIR, "database", "tags.csv")
        with open(csv_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                tag = TagsDB(
                    userId=int(row["userId"]),
                    movieId=int(row["movieId"]),
                    tag=row["tag"],
                    timestamp=int(row["timestamp"]),
                )
                db.add(tag)
        db.commit()

    db.close()


@app.on_event("startup")
def on_startup():
    # przy starcie serwera: tworzymy tabele i ewentualnie ładujemy dane
    init_db()


# ---------- ENDPOINTY NA BAZIE ----------

@app.get("/movies", response_model=List[Movie])
def get_movies(db: Session = Depends(get_db)):
    movies = db.query(MovieDB).all()
    return movies


@app.get("/ratings", response_model=List[Rating])
def get_ratings(db: Session = Depends(get_db)):
    ratings = db.query(RatingDB).all()
    return ratings

@app.get("/links", response_model=List[links])
def get_links(db: Session = Depends(get_db)):
    links = db.query(linksDB).all()
    return links

@app.get("/tags", response_model=List[Tags])
def get_tags(db: Session = Depends(get_db)):
    tags = db.query(TagsDB).all()
    return tags
