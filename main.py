from fastapi import FastAPI
from database import engine, Base
from routes.user_routes import router as user_router

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title='Travel Vlogging API',
    description='Backend API for Travel Vlogging Project',
    version='1.0.0'
)

app.include_router(user_router)

@app.get('/')
def home():
    return {'message': 'Travel Vlogging Backend Running'}