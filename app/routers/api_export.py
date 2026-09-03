from fastapi import APIRouter, Depends, Response, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services import export as export_service

router = APIRouter(prefix="/api/export", tags=["Corpus Export"])

@router.get("/corpus")
def download_corpus_export(db: Session = Depends(get_db)):
    """
    Downloads the entire oral corpus as a structured ZIP file (audio, metadata CSVs, Praat TextGrids).
    """
    try:
        zip_bytes, filename = export_service.export_corpus_zip(db)
        return Response(
            content=zip_bytes,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur d'exportation du corpus: {e}")
