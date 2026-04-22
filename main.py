import os
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine, Base
from routes.user_routes import profile_router, router as user_router

load_dotenv()

cors_origins = os.getenv("CORS_ORIGINS", "").split(",")

Base.metadata.create_all(bind=engine)

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

@app.get('/')
def home():
    return {'message': 'Travel Vlogging Backend Running'}