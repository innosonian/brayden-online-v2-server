from fastapi import FastAPI, Depends, status
from fastapi.middleware.cors import CORSMiddleware

from sqlalchemy.orm import Session
from database import get_db, Base, engine

from models.model import CPRGuideline

from apis import api

Base.metadata.create_all(bind=engine)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api.api_router)


@app.get("/")
async def root():
    return "Hi"


@app.get("/health-check")
async def health_check():
    return status.HTTP_200_OK


@app.post("/cpr_guidelines")
async def create_cpr_guideline(data: dict, db: Session = Depends(get_db)):
    db.expire_on_commit = False

    cpr_guideline = CPRGuideline(
        title=data["title"],
        compression_depth=data["compression_depth"],
        ventilation_volume=data["ventilation_volume"])
    db.add(cpr_guideline)
    db.commit()
    db.refresh(cpr_guideline)

    return cpr_guideline


@app.get("/cpr_guidelines")
async def get_cpr_guidelines(db: Session = Depends(get_db)):
    return db.query(CPRGuideline).all()


