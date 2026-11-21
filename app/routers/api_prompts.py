from typing import List, Optional, Set
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.prompt import PromptCreate, PromptRead
from app.services import prompt as prompt_service
from app.services.storage import storage_service

router = APIRouter(prefix="/api/prompts", tags=["Prompts"])


class PromptRotationResponse(BaseModel):
    prompt: Optional[PromptRead] = None
    completed_in_session: int
    remaining_for_speaker: int
    target_task: str


@router.get("", response_model=List[PromptRead])
def list_prompts(
    skip: int = 0,
    limit: int = 100,
    active_only: bool = False,
    prompt_type: Optional[str] = None,
    db: Session = Depends(get_db),
):
    return prompt_service.get_prompts(
        db, skip=skip, limit=limit, active_only=active_only, prompt_type=prompt_type
    )


@router.post("", response_model=PromptRead, status_code=status.HTTP_201_CREATED)
def create_prompt(
    prompt_in: PromptCreate,
    db: Session = Depends(get_db),
):
    return prompt_service.create_prompt(db, prompt_in)


@router.get("/next", response_model=PromptRotationResponse)
def get_next_prompt_for_session(
    session_id: UUID = Query(..., description="ID de la session en cours"),
    exclude_ids: Optional[str] = Query(
        None, description="IDs de prompts à ignorer (séparés par des virgules)"
    ),
    db: Session = Depends(get_db),
):
    parsed_excludes: Set[UUID] = set()
    if exclude_ids:
        for raw in exclude_ids.split(","):
            raw = raw.strip()
            if raw:
                try:
                    parsed_excludes.add(UUID(raw))
                except ValueError:
                    pass
    try:
        return prompt_service.get_next_prompt_for_session(
            db, session_id=session_id, exclude_ids=parsed_excludes
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{prompt_id}", response_model=PromptRead)
def get_prompt(
    prompt_id: UUID,
    db: Session = Depends(get_db),
):
    prompt = prompt_service.get_prompt_by_id(db, prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt non trouvé")
    return prompt


@router.post("/{prompt_id}/media", response_model=PromptRead)
async def upload_prompt_media(
    prompt_id: UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    image_bytes = await file.read()
    try:
        return prompt_service.attach_prompt_media(
            db=db,
            prompt_id=prompt_id,
            image_bytes=image_bytes,
            content_type=file.content_type or "image/jpeg",
        )
    except ValueError as e:
        code = 404 if "non trouvé" in str(e).lower() else 400
        raise HTTPException(status_code=code, detail=str(e))


@router.get("/{prompt_id}/media")
def stream_prompt_media(
    prompt_id: UUID,
    db: Session = Depends(get_db),
):
    prompt = prompt_service.get_prompt_by_id(db, prompt_id)
    if not prompt or not prompt.media_object_key:
        raise HTTPException(status_code=404, detail="Image du prompt non trouvée")

    try:
        stream = storage_service.get_object_stream(str(prompt.media_object_key))
        media_type = prompt.media_content_type or "image/jpeg"
        return StreamingResponse(
            stream.stream(32768),
            media_type=media_type,
            headers={"Cache-Control": "public, max-age=86400"},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur de lecture image MinIO: {e}")


@router.post("/{prompt_id}/toggle", response_model=PromptRead)
def toggle_prompt(
    prompt_id: UUID,
    db: Session = Depends(get_db),
):
    prompt = prompt_service.toggle_prompt_active(db, prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt non trouvé")
    return prompt
