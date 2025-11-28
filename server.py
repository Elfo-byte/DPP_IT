from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from typing import List, Optional

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

@app.post("/movies", response_model=Movie, status_code=201)
def create_movie(movie: Movie, db: Session = Depends(get_db)):
    # ignorujemy ewentualne id z requestu
    movie_data = movie.dict(exclude={"id"})
    db_movie = MovieDB(**movie_data)
    db.add(db_movie)
    db.commit()
    db.refresh(db_movie)
    return db_movie


@app.get("/movies/{movie_id}", response_model=Movie)
def get_movie(movie_id: int, db: Session = Depends(get_db)):
    # korzystamy z "biznesowego" movieId, nie z auto-id
    db_movie = db.query(MovieDB).filter(MovieDB.movieId == movie_id).first()
    if db_movie is None:
        raise HTTPException(status_code=404, detail="Movie not found")
    return db_movie


@app.put("/movies/{movie_id}", response_model=Movie)
def update_movie(movie_id: int, movie: Movie, db: Session = Depends(get_db)):
    db_movie = db.query(MovieDB).filter(MovieDB.movieId == movie_id).first()
    if db_movie is None:
        raise HTTPException(status_code=404, detail="Movie not found")

    for field, value in movie.dict(exclude={"id"}).items():
        setattr(db_movie, field, value)

    db.commit()
    db.refresh(db_movie)
    return db_movie


@app.delete("/movies/{movie_id}", status_code=204)
def delete_movie(movie_id: int, db: Session = Depends(get_db)):
    db_movie = db.query(MovieDB).filter(MovieDB.movieId == movie_id).first()
    if db_movie is None:
        raise HTTPException(status_code=404, detail="Movie not found")

    db.delete(db_movie)
    db.commit()
    return Response(status_code=204)



@app.get("/ratings", response_model=List[Rating])
def get_ratings(db: Session = Depends(get_db)):
    ratings = db.query(RatingDB).all()
    return ratings

@app.post("/ratings", response_model=Rating, status_code=201)
def create_rating(rating: Rating, db: Session = Depends(get_db)):
    rating_data = rating.dict(exclude={"id"})
    db_rating = RatingDB(**rating_data)
    db.add(db_rating)
    db.commit()
    db.refresh(db_rating)
    return db_rating


@app.get("/ratings/{rating_id}", response_model=Rating)
def get_rating(rating_id: int, db: Session = Depends(get_db)):
    db_rating = db.query(RatingDB).filter(RatingDB.id == rating_id).first()
    if db_rating is None:
        raise HTTPException(status_code=404, detail="Rating not found")
    return db_rating


@app.put("/ratings/{rating_id}", response_model=Rating)
def update_rating(rating_id: int, rating: Rating, db: Session = Depends(get_db)):
    db_rating = db.query(RatingDB).filter(RatingDB.id == rating_id).first()
    if db_rating is None:
        raise HTTPException(status_code=404, detail="Rating not found")

    for field, value in rating.dict(exclude={"id"}).items():
        setattr(db_rating, field, value)

    db.commit()
    db.refresh(db_rating)
    return db_rating


@app.delete("/ratings/{rating_id}", status_code=204)
def delete_rating(rating_id: int, db: Session = Depends(get_db)):
    db_rating = db.query(RatingDB).filter(RatingDB.id == rating_id).first()
    if db_rating is None:
        raise HTTPException(status_code=404, detail="Rating not found")

    db.delete(db_rating)
    db.commit()
    return Response(status_code=204)




@app.get("/links", response_model=List[links])
def get_links(db: Session = Depends(get_db)):
    links = db.query(linksDB).all()
    return links

@app.post("/links", response_model=links, status_code=201)
def create_link(link: links, db: Session = Depends(get_db)):
    link_data = link.dict(exclude={"id"})
    db_link = linksDB(**link_data)
    db.add(db_link)
    db.commit()
    db.refresh(db_link)
    return db_link


@app.get("/links/{movie_id}", response_model=links)
def get_link(movie_id: int, db: Session = Depends(get_db)):
    db_link = db.query(linksDB).filter(linksDB.movieId == movie_id).first()
    if db_link is None:
        raise HTTPException(status_code=404, detail="Link not found")
    return db_link


@app.put("/links/{movie_id}", response_model=links)
def update_link(movie_id: int, link: links, db: Session = Depends(get_db)):
    db_link = db.query(linksDB).filter(linksDB.movieId == movie_id).first()
    if db_link is None:
        raise HTTPException(status_code=404, detail="Link not found")

    for field, value in link.dict(exclude={"id"}).items():
        setattr(db_link, field, value)

    db.commit()
    db.refresh(db_link)
    return db_link


@app.delete("/links/{movie_id}", status_code=204)
def delete_link(movie_id: int, db: Session = Depends(get_db)):
    db_link = db.query(linksDB).filter(linksDB.movieId == movie_id).first()
    if db_link is None:
        raise HTTPException(status_code=404, detail="Link not found")

    db.delete(db_link)
    db.commit()
    return Response(status_code=204)


@app.get("/tags", response_model=List[Tags])
def get_tags(db: Session = Depends(get_db)):
    tags = db.query(TagsDB).all()
    return tags

@app.post("/tags", response_model=Tags, status_code=201)
def create_tag(tag: Tags, db: Session = Depends(get_db)):
    tag_data = tag.dict(exclude={"id"})
    db_tag = TagsDB(**tag_data)
    db.add(db_tag)
    db.commit()
    db.refresh(db_tag)
    return db_tag


@app.get("/tags/{tag_id}", response_model=Tags)
def get_tag(tag_id: int, db: Session = Depends(get_db)):
    db_tag = db.query(TagsDB).filter(TagsDB.id == tag_id).first()
    if db_tag is None:
        raise HTTPException(status_code=404, detail="Tag not found")
    return db_tag


@app.put("/tags/{tag_id}", response_model=Tags)
def update_tag(tag_id: int, tag: Tags, db: Session = Depends(get_db)):
    db_tag = db.query(TagsDB).filter(TagsDB.id == tag_id).first()
    if db_tag is None:
        raise HTTPException(status_code=404, detail="Tag not found")

    for field, value in tag.dict(exclude={"id"}).items():
        setattr(db_tag, field, value)

    db.commit()
    db.refresh(db_tag)
    return db_tag


@app.delete("/tags/{tag_id}", status_code=204)
def delete_tag(tag_id: int, db: Session = Depends(get_db)):
    db_tag = db.query(TagsDB).filter(TagsDB.id == tag_id).first()
    if db_tag is None:
        raise HTTPException(status_code=404, detail="Tag not found")

    db.delete(db_tag)
    db.commit()
    return Response(status_code=204)
