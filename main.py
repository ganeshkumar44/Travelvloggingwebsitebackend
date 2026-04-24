import os
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from database import engine, Base
import models.story_model  # noqa: F401  # register Story / Tag metadata
from routes.story_routes import router as story_router
from routes.user_routes import profile_router, router as user_router

load_dotenv()

cors_origins = os.getenv("CORS_ORIGINS", "").split(",")

Base.metadata.create_all(bind=engine)

_base_dir = os.path.dirname(os.path.abspath(__file__))
_upload_dir = os.path.join(_base_dir, 'uploads')
os.makedirs(_upload_dir, exist_ok=True)

app = FastAPI(
    title='Travel Vlogging API',
    description='Backend API for Travel Vlogging Project',
    version='1.0.0'
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(user_router)
app.include_router(profile_router)
app.include_router(story_router)
app.mount('/uploads', StaticFiles(directory=_upload_dir), name='uploads')

@app.get('/')
def home():
    return {'message': 'Travel Vlogging Backend Running'}