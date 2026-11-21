from typing import Optional
from fastapi import APIRouter, Depends, Response, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services import auth as auth_service
from app.services import export as export_service

router = APIRouter(
    prefix="/api/export",
    tags=["Corpus Export"],
    dependencies=[Depends(auth_service.require_api_roles("admin"))],
)


@router.get("/corpus")
def download_corpus_export(
    include_unvalidated: bool = Query(
        False,
        description="Inclure aussi les audios non encore validés (déconseillé pour l'entraînement ML).",
    ),
    target_task: Optional[str] = Query(
        None,
        description="Filtrer par type de session : 'asr' ou 'tts'.",
    ),
    db: Session = Depends(get_db),
):
    """
    Downloads the oral corpus as a structured ZIP archive with speaker-disjoint splits,
    metadata CSVs, export_manifest.json, Praat TextGrids, and CC-BY-4.0 notice.
    """
    if target_task and target_task not in {"asr", "tts"}:
        raise HTTPException(status_code=400, detail="target_task doit être 'asr' ou 'tts'")

    try:
        zip_bytes, filename = export_service.export_corpus_zip(
            db,
            include_unvalidated=include_unvalidated,
            target_task=target_task,
        )
        return Response(
            content=zip_bytes,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur d'exportation du corpus: {e}")
