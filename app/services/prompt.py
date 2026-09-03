from typing import List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models import Prompt
from app.schemas.prompt import PromptCreate

def generate_prompt_code(db: Session) -> str:
    count = db.query(func.count(Prompt.id)).scalar() or 0
    return f"PRM_{count + 1:06d}"

def create_prompt(db: Session, prompt_in: PromptCreate) -> Prompt:
    code = prompt_in.prompt_code or generate_prompt_code(db)
    db_prompt = Prompt(
        prompt_code=code,
        prompt_type=prompt_in.prompt_type,
        title=prompt_in.title,
        description=prompt_in.description,
        content=prompt_in.content,
        language=prompt_in.language,
        topic=prompt_in.topic,
        difficulty=prompt_in.difficulty,
        active=prompt_in.active
    )
    db.add(db_prompt)
    db.commit()
    db.refresh(db_prompt)
    return db_prompt

def get_prompts(db: Session, skip: int = 0, limit: int = 100, active_only: bool = False) -> List[Prompt]:
    q = db.query(Prompt)
    if active_only:
        q = q.filter(Prompt.active == True)
    return q.order_by(Prompt.created_at.desc()).offset(skip).limit(limit).all()

def get_prompt_by_id(db: Session, prompt_id: UUID) -> Optional[Prompt]:
    return db.query(Prompt).filter(Prompt.id == prompt_id).first()

def toggle_prompt_active(db: Session, prompt_id: UUID) -> Optional[Prompt]:
    prompt = get_prompt_by_id(db, prompt_id)
    if prompt:
        prompt.active = not prompt.active
        db.commit()
        db.refresh(prompt)
    return prompt
