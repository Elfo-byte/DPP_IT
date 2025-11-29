
# LAB 02

## Project Setup

This project demonstrates basic Python API setup and environment management.

### 1. Create and activate a virtual environment (Windows)

```powershell
python -m venv venv
.\venv\Scripts\activate
```

### 2. Install dependencies

```powershell
pip install -r requirements.txt
```

### 3. Run the API server (example for FastAPI)

```powershell
uvicorn main:app --reload
```

- Make sure you are in the `src` directory when running the server command.
- Visit http://127.0.0.1:8000/ in your browser to check if the API is running.

### 4. Do tworzenia userów zaloguj się na admina, wymagane żeby token JWT był nadany + rola admin


