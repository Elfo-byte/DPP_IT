from fastapi import FastAPI
import csv
import os

app = FastAPI()

# Tags data model
class Tags:
    def __init__(self, userId, movieId, tag, timestamp):
        self.userId = userId
        self.movieId = movieId
        self.tag = tag
        self.timestamp = timestamp

@app.get("/tags")
def get_tags():
    tags = []
    csv_path = os.path.join(os.path.dirname(__file__), "database", "tags.csv")
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            tag = Tags(row["userId"], row["movieId"], row["tag"], row["timestamp"])
            tags.append(tag.__dict__)
    return tags

# Ratings data model
class Ratings:
    def __init__(self, userId, movieId, rating, timestamp):
        self.userId = userId
        self.movieId = movieId
        self.rating = rating
        self.timestamp = timestamp

@app.get("/ratings")
def get_ratings():
    ratings = []
    csv_path = os.path.join(os.path.dirname(__file__), "database", "ratings.csv")
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rating = Ratings(row["userId"], row["movieId"], row["rating"], row["timestamp"])
            ratings.append(rating.__dict__)
    return ratings

# Links data model
class Links:
    def __init__(self, movieId, imdbId, tmdbId):
        self.movieId = movieId
        self.imdbId = imdbId
        self.tmdbId = tmdbId

@app.get("/links")
def get_links():
    links = []
    csv_path = os.path.join(os.path.dirname(__file__), "database", "links.csv")
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            link = Links(row["movieId"], row["imdbId"], row["tmdbId"])
            links.append(link.__dict__)
    return links

@app.get("/")
def read_root():
    return {"hello": "world"}

# Movie data model
class Movie:
    def __init__(self, movieId, title, genres):
        self.movieId = movieId
        self.title = title
        self.genres = genres

@app.get("/movies")
def get_movies():
    movies = []
    csv_path = os.path.join(os.path.dirname(__file__), "database", "movies.csv")
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            movie = Movie(row["movieId"], row["title"], row["genres"])
            movies.append(movie.__dict__)
    return movies