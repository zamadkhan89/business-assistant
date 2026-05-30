"""Glossary CRUD API."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.db import get_db
from app.models.glossary import GlossaryEntry
from app.models.user import User

router = APIRouter(prefix="/glossary", tags=["glossary"])


class GlossaryBody(BaseModel):
    term: str
    definition: str


@router.get("")
async def list_entries(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(GlossaryEntry)
        .where(GlossaryEntry.user_id == current_user.id)
        .order_by(GlossaryEntry.term)
    )
    entries = result.scalars().all()
    return [{"id": e.id, "term": e.term, "definition": e.definition} for e in entries]


@router.post("", status_code=201)
async def create_entry(
    body: GlossaryBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not body.term.strip() or not body.definition.strip():
        raise HTTPException(status_code=400, detail="term and definition are required")
    entry = GlossaryEntry(user_id=current_user.id, term=body.term.strip(), definition=body.definition.strip())
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return {"id": entry.id, "term": entry.term, "definition": entry.definition}


@router.put("/{entry_id}")
async def update_entry(
    entry_id: str,
    body: GlossaryBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    entry = await db.get(GlossaryEntry, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Entry not found")
    if entry.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your entry")
    if not body.term.strip() or not body.definition.strip():
        raise HTTPException(status_code=400, detail="term and definition are required")
    entry.term = body.term.strip()
    entry.definition = body.definition.strip()
    await db.commit()
    return {"id": entry.id, "term": entry.term, "definition": entry.definition}


@router.delete("/{entry_id}", status_code=204)
async def delete_entry(
    entry_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    entry = await db.get(GlossaryEntry, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Entry not found")
    if entry.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your entry")
    await db.delete(entry)
    await db.commit()
