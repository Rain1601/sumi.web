"""Annotations CRUD API — human evaluation of conversation quality."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func

from backend.api.deps import DbSession
from backend.db.models import Annotation, gen_uuid

router = APIRouter()


class AnnotationResponse(BaseModel):
    id: str
    conversation_id: str
    message_id: str | None
    turn_index: int | None
    annotation_type: str
    rating: int | None
    labels: list | None
    corrected_text: str | None
    expected_response: str | None
    notes: str | None
    annotator: str


class AnnotationCreate(BaseModel):
    conversation_id: str
    message_id: str | None = None
    turn_index: int | None = None
    annotation_type: str  # "asr" | "response" | "skill" | "overall"
    rating: int | None = None
    labels: list | None = None
    corrected_text: str | None = None
    expected_response: str | None = None
    notes: str | None = None
    annotator: str = "human"


class AnnotationUpdate(BaseModel):
    rating: int | None = None
    labels: list | None = None
    corrected_text: str | None = None
    expected_response: str | None = None
    notes: str | None = None


class AnnotationStats(BaseModel):
    total: int
    avg_rating: float | None
    by_type: dict[str, int]
    by_label: dict[str, int]


def _to_response(a: Annotation) -> AnnotationResponse:
    return AnnotationResponse(
        id=a.id, conversation_id=a.conversation_id, message_id=a.message_id,
        turn_index=a.turn_index, annotation_type=a.annotation_type,
        rating=a.rating, labels=a.labels, corrected_text=a.corrected_text,
        expected_response=a.expected_response, notes=a.notes, annotator=a.annotator,
    )


@router.get("/", response_model=list[AnnotationResponse])
async def list_annotations(conversation_id: str | None = None, db: DbSession = None):
    q = select(Annotation)
    if conversation_id:
        q = q.where(Annotation.conversation_id == conversation_id)
    q = q.order_by(Annotation.created_at)
    result = await db.execute(q)
    return [_to_response(a) for a in result.scalars().all()]


@router.post("/", response_model=AnnotationResponse)
async def create_annotation(req: AnnotationCreate, db: DbSession):
    ann = Annotation(
        id=gen_uuid(),
        conversation_id=req.conversation_id,
        message_id=req.message_id,
        turn_index=req.turn_index,
        annotation_type=req.annotation_type,
        rating=req.rating,
        labels=req.labels,
        corrected_text=req.corrected_text,
        expected_response=req.expected_response,
        notes=req.notes,
        annotator=req.annotator,
    )
    db.add(ann)
    await db.commit()
    await db.refresh(ann)
    return _to_response(ann)


@router.patch("/{annotation_id}", response_model=AnnotationResponse)
async def update_annotation(annotation_id: str, req: AnnotationUpdate, db: DbSession):
    result = await db.execute(select(Annotation).where(Annotation.id == annotation_id))
    ann = result.scalar_one_or_none()
    if not ann:
        raise HTTPException(404, "Annotation not found")
    for field in ["rating", "labels", "corrected_text", "expected_response", "notes"]:
        value = getattr(req, field)
        if value is not None:
            setattr(ann, field, value)
    await db.commit()
    await db.refresh(ann)
    return _to_response(ann)


@router.delete("/{annotation_id}")
async def delete_annotation(annotation_id: str, db: DbSession):
    result = await db.execute(select(Annotation).where(Annotation.id == annotation_id))
    ann = result.scalar_one_or_none()
    if not ann:
        raise HTTPException(404, "Annotation not found")
    await db.delete(ann)
    await db.commit()
    return {"ok": True}


@router.get("/stats", response_model=AnnotationStats)
async def annotation_stats(conversation_id: str | None = None, db: DbSession = None):
    q = select(Annotation)
    if conversation_id:
        q = q.where(Annotation.conversation_id == conversation_id)
    result = await db.execute(q)
    annotations = list(result.scalars().all())

    ratings = [a.rating for a in annotations if a.rating is not None]
    by_type: dict[str, int] = {}
    by_label: dict[str, int] = {}

    for a in annotations:
        by_type[a.annotation_type] = by_type.get(a.annotation_type, 0) + 1
        for label in (a.labels or []):
            by_label[label] = by_label.get(label, 0) + 1

    return AnnotationStats(
        total=len(annotations),
        avg_rating=round(sum(ratings) / len(ratings), 2) if ratings else None,
        by_type=by_type,
        by_label=by_label,
    )
