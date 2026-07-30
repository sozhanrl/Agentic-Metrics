from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app import crud, schemas

router = APIRouter(prefix="/feedback", tags=["Feedback"])


@router.post("", response_model=schemas.FeedbackResponse)
def submit_feedback(feedback: schemas.FeedbackCreate, db: Session = Depends(get_db)):
    return crud.create_feedback(db, feedback)


@router.get("/{recommendation_id}", response_model=list[schemas.FeedbackResponse])
def get_feedback(recommendation_id: int, db: Session = Depends(get_db)):
    return crud.get_feedback_for_recommendation(db, recommendation_id)
