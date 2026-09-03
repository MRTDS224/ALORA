from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.prompt import PromptCreate, PromptRead
from app.services import prompt as prompt_service

router = APIRouter(prefix="/api/prompts", tags=["Prompts"])

@router.get("", response_model=List[PromptRead])
def list_prompts(
    skip: int = 0,
    limit: int = 100,
    active_only: bool = False,
    db: Session = Depends(get_db)
):
    return prompt_service.get_prompts(db, skip=skip, limit=limit, active_only=active_only)

@router.post("", response_model=PromptRead, status_code=status.HTTP_201_CREATED)
def create_prompt(
    prompt_in: PromptCreate,
    db: Session = Depends(get_db)
):
    return prompt_service.create_prompt(db, prompt_in)

@router.get("/{prompt_id}", response_model=PromptRead)
def get_prompt(
    prompt_id: UUID,
    db: Session = Depends(get_db)
):
    prompt = prompt_service.get_prompt_by_id(db, prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt non trouvé")
    return prompt

@router.post("/{prompt_id}/toggle", response_model=PromptRead)
def toggle_prompt(
    prompt_id: UUID,
    db: Session = Depends(get_db)
):
    prompt = prompt_service.toggle_prompt_active(db, prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt non trouvé")
    return prompt
