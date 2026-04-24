import os
import uuid
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from models.story_model import Story, StoryReaction, Tag
from models.user_model import User


STORY_TAG_MAX = 100
STORY_IMAGE_MAX_BYTES = 10 * 1024 * 1024
IMAGE_TYPES_TO_EXT = {
    'image/jpeg': '.jpg',
    'image/jpg': '.jpg',
    'image/png': '.png',
    'image/gif': '.gif',
    'image/webp': '.webp',
}


def get_user_id_by_email(db: Session, email: str) -> int:
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail='User not found')
    return user.id


def _dedupe_tag_strings(tag_list: Optional[list[str]]) -> list[str]:
    if not tag_list:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for raw in tag_list:
        s = raw.strip()
        if not s:
            continue
        key = s.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
    return out


def _get_or_create_tag(db: Session, display_name: str) -> Tag:
    key = display_name.strip()[:STORY_TAG_MAX]
    if not key:
        raise HTTPException(status_code=400, detail='Invalid tag value')
    key_lower = key.lower()
    existing = db.query(Tag).filter(func.lower(Tag.name) == key_lower).first()
    if existing:
        return existing
    tag = Tag(name=key)
    db.add(tag)
    db.flush()
    return tag


def save_uploaded_story_image_bytes(
    body: bytes,
    content_type: Optional[str],
    storage_root: str,
) -> str:
    if not body:
        raise HTTPException(status_code=400, detail='Empty image file')
    if len(body) > STORY_IMAGE_MAX_BYTES:
        raise HTTPException(status_code=400, detail='Image file is too large')
    raw = (content_type or '').split(';', 1)[0].strip().lower()
    if raw == 'image/jpg':
        raw = 'image/jpeg'
    if raw not in IMAGE_TYPES_TO_EXT:
        raise HTTPException(
            status_code=400,
            detail='Image must be jpeg, png, gif, or webp',
        )
    ext = IMAGE_TYPES_TO_EXT[raw]
    name = f'{uuid.uuid4().hex}{ext}'
    dest_dir = os.path.join(storage_root, 'stories')
    os.makedirs(dest_dir, exist_ok=True)
    path = os.path.join(dest_dir, name)
    with open(path, 'wb') as f:
        f.write(body)
    return f'/uploads/stories/{name}'


def create_story_record(
    db: Session,
    user_id: int,
    title: str,
    description: str,
    location: Optional[str],
    image_url: str,
    tag_strings: Optional[list[str]],
) -> Story:
    if len(description) < 500:
        raise HTTPException(
            status_code=400,
            detail='Description is required and must be at least 500 characters',
        )
    if not image_url or not str(image_url).strip():
        raise HTTPException(status_code=400, detail='Image is required')
    loc: Optional[str] = None
    if location is not None:
        t = str(location).strip()
        if t:
            loc = t[:500]

    display_tags = _dedupe_tag_strings(tag_strings)
    tag_values_for_array = [t for t in display_tags] if display_tags else None

    story = Story(
        user_id=user_id,
        title=title[:500].strip() if title else title,
        description=description,
        location=loc,
        image=image_url.strip()[:20_000],
        tags=tag_values_for_array,
    )
    db.add(story)
    db.flush()

    for t in display_tags:
        story.tag_links.append(_get_or_create_tag(db, t))

    db.commit()
    db.refresh(story)
    return story


REACTION_LIKE = 'like'
REACTION_DISLIKE = 'dislike'


def _reaction_type_counts_for_story(db: Session, story_id: int) -> tuple[int, int]:
    total_likes = (
        db.query(StoryReaction)
        .filter(
            StoryReaction.story_id == story_id,
            StoryReaction.reaction_type == REACTION_LIKE,
        )
        .count()
    )
    total_dislikes = (
        db.query(StoryReaction)
        .filter(
            StoryReaction.story_id == story_id,
            StoryReaction.reaction_type == REACTION_DISLIKE,
        )
        .count()
    )
    return total_likes, total_dislikes


def react_to_story(
    db: Session,
    user_id: int,
    story_id: int,
    reaction_type: str,
) -> dict:
    story = db.query(Story).filter(Story.id == story_id).first()
    if not story:
        raise HTTPException(status_code=404, detail='Story not found')

    existing = (
        db.query(StoryReaction)
        .filter(StoryReaction.story_id == story_id, StoryReaction.user_id == user_id)
        .first()
    )

    if existing is None:
        db.add(
            StoryReaction(
                story_id=story_id,
                user_id=user_id,
                reaction_type=reaction_type,
            )
        )
    elif existing.reaction_type == reaction_type:
        db.delete(existing)
    else:
        existing.reaction_type = reaction_type

    db.commit()
    total_likes, total_dislikes = _reaction_type_counts_for_story(db, story_id)
    return {
        'message': 'Reaction updated successfully',
        'total_likes': total_likes,
        'total_dislikes': total_dislikes,
    }
