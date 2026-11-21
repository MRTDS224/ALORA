from typing import List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models import Segment, WordAnnotation, Recording, Transcription
from app.schemas.segment import SegmentCreate, WordAnnotationCreate

def generate_segment_code(db: Session) -> str:
    last = (
        db.query(Segment.segment_code)
        .filter(Segment.segment_code.like("SEG_%"))
        .order_by(Segment.segment_code.desc())
        .first()
    )
    next_num = 1
    if last and last[0]:
        try:
            next_num = int(str(last[0]).split("_", 1)[1]) + 1
        except (ValueError, IndexError):
            next_num = (db.query(func.count(Segment.id)).scalar() or 0) + 1
    return f"SEG_{next_num:06d}"

def create_segment(db: Session, segment_in: SegmentCreate) -> Segment:
    code = generate_segment_code(db)
    db_segment = Segment(
        recording_id=segment_in.recording_id,
        segment_code=code,
        start_time=segment_in.start_time,
        end_time=segment_in.end_time,
        audio_object_key=segment_in.audio_object_key
    )
    db.add(db_segment)
    db.commit()
    db.refresh(db_segment)
    return db_segment

def get_segments_by_recording(db: Session, recording_id: UUID) -> List[Segment]:
    return db.query(Segment).filter(Segment.recording_id == recording_id).order_by(Segment.start_time.asc()).all()

def create_word_annotation(db: Session, word_in: WordAnnotationCreate) -> WordAnnotation:
    db_word = WordAnnotation(
        recording_id=word_in.recording_id,
        transcription_id=word_in.transcription_id,
        word=word_in.word,
        start_time=word_in.start_time,
        end_time=word_in.end_time,
        normalized_form=word_in.normalized_form,
        annotation_type=word_in.annotation_type,
        value=word_in.value,
        annotator=word_in.annotator
    )
    db.add(db_word)
    db.commit()
    db.refresh(db_word)
    return db_word

def get_word_annotations_by_recording(db: Session, recording_id: UUID) -> List[WordAnnotation]:
    return db.query(WordAnnotation).filter(WordAnnotation.recording_id == recording_id).order_by(WordAnnotation.start_time.asc()).all()

def generate_praat_textgrid(db: Session, recording_id: UUID) -> str:
    """
    Generates a Praat .TextGrid (ooTextFile) string representation
    for a given recording with transcription and word-level intervals.
    """
    recording = db.query(Recording).filter(Recording.id == recording_id).first()
    if not recording:
        raise ValueError("Enregistrement non trouvé")

    max_duration = float(recording.duration_seconds or 10.0)
    
    # Get latest transcription
    transcription = db.query(Transcription).filter(
        Transcription.recording_id == recording_id
    ).order_by(Transcription.version.desc()).first()

    trans_text = transcription.text if transcription else ""
    words = get_word_annotations_by_recording(db, recording_id)

    # Build Praat TextGrid format
    lines = [
        'File type = "ooTextFile"',
        'Object class = "TextGrid"',
        '',
        'xmin = 0.0',
        f'xmax = {max_duration:.4f}',
        'tiers? <exists>',
        'size = 2',
        'item []:',
        '    item [1]:',
        '        class = "IntervalTier"',
        '        name = "transcription"',
        '        xmin = 0.0',
        f'        xmax = {max_duration:.4f}',
        '        intervals: size = 1',
        '        intervals [1]:',
        '            xmin = 0.0',
        f'            xmax = {max_duration:.4f}',
        f'            text = "{trans_text}"',
        '    item [2]:',
        '        class = "IntervalTier"',
        '        name = "words"',
        '        xmin = 0.0',
        f'        xmax = {max_duration:.4f}'
    ]

    if not words:
        lines.extend([
            '        intervals: size = 1',
            '        intervals [1]:',
            '            xmin = 0.0',
            f'            xmax = {max_duration:.4f}',
            f'            text = "{trans_text}"'
        ])
    else:
        lines.append(f'        intervals: size = {len(words)}')
        for idx, w in enumerate(words, start=1):
            w_xmin = float(w.start_time or 0.0)
            w_xmax = float(w.end_time or max_duration)
            lines.extend([
                f'        intervals [{idx}]:',
                f'            xmin = {w_xmin:.4f}',
                f'            xmax = {w_xmax:.4f}',
                f'            text = "{w.word}"'
            ])

    return "\n".join(lines)
