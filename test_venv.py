import sys
print("Python executable:", sys.executable)
print("Python version:", sys.version)

try:
    import fastapi
    print("FastAPI version:", fastapi.__version__)
except ImportError as e:
    print("FastAPI import error:", e)

try:
    import uvicorn
    print("Uvicorn version:", uvicorn.__version__)
except ImportError as e:
    print("Uvicorn import error:", e)

try:
    import sqlalchemy
    print("SQLAlchemy version:", sqlalchemy.__version__)
except ImportError as e:
    print("SQLAlchemy import error:", e)

try:
    import pydantic
    print("Pydantic version:", pydantic.__version__)
except ImportError as e:
    print("Pydantic import error:", e)

try:
    import pydantic_settings
    print("Pydantic-settings version:", pydantic_settings.__version__)
except ImportError as e:
    print("Pydantic-settings import error:", e)
