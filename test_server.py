# test_server.py
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from server import app, Base, get_db, MovieDB, RatingDB, linksDB, TagsDB


# --- osobna baza testowa ---

TEST_DB_URL = "sqlite:///./test.db"

engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# --- override dependency get_db tak, żeby API używało testowej bazy ---

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


# --- fixtury wspólne ---

@pytest.fixture
def db_session():
    """
    Czysta baza na każdy test:
    - drop_all + create_all
    - zwracamy sesję do wypełniania fixturami
    """
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client():
    return TestClient(app)


# --- fixtury danych dla poszczególnych zasobów ---

@pytest.fixture
def movies_fixture(db_session):
    movies = [
        MovieDB(movieId=1, title="Movie 1", genres="Action"),
        MovieDB(movieId=2, title="Movie 2", genres="Comedy"),
    ]
    db_session.add_all(movies)
    db_session.commit()
    return movies


@pytest.fixture
def ratings_fixture(db_session, movies_fixture):
    ratings = [
        RatingDB(userId=1, movieId=movies_fixture[0].movieId, rating=4.5, timestamp=111),
        RatingDB(userId=2, movieId=movies_fixture[1].movieId, rating=3.0, timestamp=222),
    ]
    db_session.add_all(ratings)
    db_session.commit()
    return ratings


@pytest.fixture
def links_fixture(db_session, movies_fixture):
    links = [
        linksDB(movieId=movies_fixture[0].movieId, imdbId=111111, tmdbId=222222),
        linksDB(movieId=movies_fixture[1].movieId, imdbId=333333, tmdbId=444444),
    ]
    db_session.add_all(links)
    db_session.commit()
    return links


@pytest.fixture
def tags_fixture(db_session, movies_fixture):
    tags = [
        TagsDB(userId=1, movieId=movies_fixture[0].movieId, tag="tag-a", timestamp=123),
        TagsDB(userId=2, movieId=movies_fixture[1].movieId, tag="tag-b", timestamp=456),
    ]
    db_session.add_all(tags)
    db_session.commit()
    return tags


# =========================
#   TESTY DLA /movies
# =========================

def test_movies_endpoints(client, db_session, movies_fixture):
    # a) GET lista zwraca tyle elementów, ile w fixturze
    resp = client.get("/movies")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == len(movies_fixture)
    movie_ids_from_api = sorted(m["movieId"] for m in data)
    movie_ids_from_fixture = sorted(m.movieId for m in movies_fixture)
    assert movie_ids_from_api == movie_ids_from_fixture

    # b) GET item zwraca poprawny element
    movie_id = movies_fixture[0].movieId
    resp = client.get(f"/movies/{movie_id}")
    assert resp.status_code == 200
    movie = resp.json()
    assert movie["movieId"] == movie_id
    assert movie["title"] == movies_fixture[0].title

    # c) GET item dla nieistniejącego ID -> 404
    resp = client.get("/movies/999999")
    assert resp.status_code == 404

    # d) POST dodaje nowy element
    new_movie = {
        "movieId": 10,
        "title": "New Movie",
        "genres": "Drama",
    }
    resp = client.post("/movies", json=new_movie)
    assert resp.status_code == 201
    created = resp.json()
    assert created["movieId"] == new_movie["movieId"]
    assert created["title"] == new_movie["title"]

    # sprawdzamy, że liczba elementów się zwiększyła
    resp = client.get("/movies")
    assert len(resp.json()) == len(movies_fixture) + 1

    # e) PUT aktualizuje rekord w bazie
    updated_movie = {
        "id": created.get("id"),
        "movieId": new_movie["movieId"],
        "title": "Updated Movie",
        "genres": "Drama|Comedy",
    }
    resp = client.put(f"/movies/{new_movie['movieId']}", json=updated_movie)
    assert resp.status_code == 200
    updated = resp.json()
    assert updated["title"] == "Updated Movie"
    assert updated["genres"] == "Drama|Comedy"

    # potwierdzamy zmianę jeszcze jednym GET-em
    resp = client.get(f"/movies/{new_movie['movieId']}")
    assert resp.status_code == 200
    again = resp.json()
    assert again["title"] == "Updated Movie"

    # f) DELETE usuwa element
    resp = client.delete(f"/movies/{new_movie['movieId']}")
    assert resp.status_code == 204

    # po DELETE item nie powinien istnieć
    resp = client.get(f"/movies/{new_movie['movieId']}")
    assert resp.status_code == 404


# =========================
#   TESTY DLA /ratings
# =========================

def test_ratings_endpoints(client, db_session, ratings_fixture):
    # GET lista
    resp = client.get("/ratings")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == len(ratings_fixture)

    # GET item istniejący
    rating_id = ratings_fixture[0].id
    resp = client.get(f"/ratings/{rating_id}")
    assert resp.status_code == 200
    rating = resp.json()
    assert rating["id"] == rating_id
    assert rating["rating"] == pytest.approx(ratings_fixture[0].rating)

    # GET item nieistniejący
    resp = client.get("/ratings/999999")
    assert resp.status_code == 404

    # POST nowy
    new_rating = {
        "userId": 3,
        "movieId": ratings_fixture[0].movieId,
        "rating": 5.0,
        "timestamp": 999,
    }
    resp = client.post("/ratings", json=new_rating)
    assert resp.status_code == 201
    created = resp.json()
    assert created["userId"] == 3
    assert created["rating"] == 5.0

    # PUT aktualizacja
    updated_rating = {
        "id": created["id"],
        "userId": 4,
        "movieId": ratings_fixture[0].movieId,
        "rating": 2.5,
        "timestamp": 999,
    }
    resp = client.put(f"/ratings/{created['id']}", json=updated_rating)
    assert resp.status_code == 200
    updated = resp.json()
    assert updated["userId"] == 4
    assert updated["rating"] == 2.5

    # DELETE
    resp = client.delete(f"/ratings/{created['id']}")
    assert resp.status_code == 204
    resp = client.get(f"/ratings/{created['id']}")
    assert resp.status_code == 404


# =========================
#   TESTY DLA /links
# =========================

def test_links_endpoints(client, db_session, links_fixture):
    # GET lista
    resp = client.get("/links")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == len(links_fixture)

    # GET item istniejący (po movieId)
    movie_id = links_fixture[0].movieId
    resp = client.get(f"/links/{movie_id}")
    assert resp.status_code == 200
    link = resp.json()
    assert link["movieId"] == movie_id
    assert link["imdbId"] == links_fixture[0].imdbId

    # GET item nieistniejący
    resp = client.get("/links/999999")
    assert resp.status_code == 404

    # POST nowy
    new_link = {
        "movieId": 12345,
        "imdbId": 777777,
        "tmdbId": 888888,
    }
    resp = client.post("/links", json=new_link)
    assert resp.status_code == 201
    created = resp.json()
    assert created["movieId"] == new_link["movieId"]

    # PUT aktualizacja
    updated_link = {
        "id": created.get("id"),
        "movieId": new_link["movieId"],
        "imdbId": 999999,
        "tmdbId": 111111,
    }
    resp = client.put(f"/links/{new_link['movieId']}", json=updated_link)
    assert resp.status_code == 200
    updated = resp.json()
    assert updated["imdbId"] == 999999
    assert updated["tmdbId"] == 111111

    # DELETE
    resp = client.delete(f"/links/{new_link['movieId']}")
    assert resp.status_code == 204
    resp = client.get(f"/links/{new_link['movieId']}")
    assert resp.status_code == 404


# =========================
#   TESTY DLA /tags
# =========================

def test_tags_endpoints(client, db_session, tags_fixture):
    # GET lista
    resp = client.get("/tags")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == len(tags_fixture)

    # GET item istniejący (po id)
    tag_id = tags_fixture[0].id
    resp = client.get(f"/tags/{tag_id}")
    assert resp.status_code == 200
    tag = resp.json()
    assert tag["id"] == tag_id
    assert tag["tag"] == tags_fixture[0].tag

    # GET item nieistniejący
    resp = client.get("/tags/999999")
    assert resp.status_code == 404

    # POST nowy
    new_tag = {
        "userId": 10,
        "movieId": tags_fixture[0].movieId,
        "tag": "new-tag",
        "timestamp": 9999,
    }
    resp = client.post("/tags", json=new_tag)
    assert resp.status_code == 201
    created = resp.json()
    assert created["tag"] == "new-tag"

    # PUT aktualizacja
    updated_tag = {
        "id": created["id"],
        "userId": 10,
        "movieId": tags_fixture[0].movieId,
        "tag": "updated-tag",
        "timestamp": 9999,
    }
    resp = client.put(f"/tags/{created['id']}", json=updated_tag)
    assert resp.status_code == 200
    updated = resp.json()
    assert updated["tag"] == "updated-tag"

    # DELETE
    resp = client.delete(f"/tags/{created['id']}")
    assert resp.status_code == 204
    resp = client.get(f"/tags/{created['id']}")
    assert resp.status_code == 404
