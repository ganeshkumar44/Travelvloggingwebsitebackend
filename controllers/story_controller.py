import os
import uuid
from datetime import datetime
from typing import Any, Optional

from fastapi import HTTPException, status
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from models.story_model import Story, StoryComment, StoryReaction, Tag
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


def get_user_id_and_role_by_email(db: Session, email: str) -> tuple[int, str]:
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail='User not found')
    role = (user.role or 'user').strip().lower()
    return user.id, role


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


def get_all_stories(db: Session) -> list[Story]:
    return db.query(Story).order_by(Story.created_at.desc()).all()


def get_story_by_id(db: Session, story_id: int) -> Story:
    story = db.query(Story).filter(Story.id == story_id).first()
    if not story:
        raise HTTPException(status_code=404, detail='Story not found')
    return story


REACTION_LIKE = 'like'
REACTION_DISLIKE = 'dislike'


def get_all_stories_v1(db: Session) -> list[dict[str, object]]:
    """
    Single query: stories JOIN users, LEFT JOIN story_reactions, aggregate likes/dislikes.
    """
    total_likes = func.coalesce(
        func.sum(
            case(
                (StoryReaction.reaction_type == REACTION_LIKE, 1),
                else_=0,
            )
        ),
        0,
    ).label("total_likes")
    total_dislikes = func.coalesce(
        func.sum(
            case(
                (StoryReaction.reaction_type == REACTION_DISLIKE, 1),
                else_=0,
            )
        ),
        0,
    ).label("total_dislikes")
    rows = (
        db.query(Story, User, total_likes, total_dislikes)
        .join(User, Story.user_id == User.id)
        .outerjoin(StoryReaction, Story.id == StoryReaction.story_id)
        .group_by(Story.id, User.id)
        .order_by(Story.created_at.desc())
        .all()
    )
    out: list[dict[str, object]] = []
    for story, user, likes, dislikes in rows:
        out.append(
            {
                "id": story.id,
                "user_id": story.user_id,
                "image": story.image,
                "title": story.title,
                "description": story.description,
                "status": story.status,
                "location": story.location,
                "tags": story.tags,
                "created_at": story.created_at,
                "updated_at": story.updated_at,
                "user": {
                    "firstname": user.firstname,
                    "lastname": user.lastname,
                    "facebook": user.facebook,
                    "twitter": user.twitter,
                    "linkedin": user.linkedin,
                    "instagram": user.instagram,
                    "youtube": user.youtube,
                    "about_author": user.about_author,
                    "profession": user.profession,
                },
                "total_likes": int(likes) if likes is not None else 0,
                "total_dislikes": int(dislikes) if dislikes is not None else 0,
            }
        )
    return out


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


def add_story_comment(
    db: Session,
    user_id: int,
    story_id: int,
    comment: str,
    parent_comment_id: Optional[int] = None,
) -> dict:
    story = db.query(Story).filter(Story.id == story_id).first()
    if not story:
        raise HTTPException(status_code=404, detail='Story not found')

    body = (comment or '').strip()
    if not body:
        raise HTTPException(status_code=400, detail='Comment cannot be empty')

    if parent_comment_id is not None:
        parent = (
            db.query(StoryComment)
            .filter(StoryComment.id == parent_comment_id)
            .first()
        )
        if not parent:
            raise HTTPException(status_code=400, detail='Parent comment not found')
        if parent.story_id != story_id:
            raise HTTPException(
                status_code=400,
                detail='Parent comment does not belong to this story',
            )

    row = StoryComment(
        story_id=story_id,
        user_id=user_id,
        parent_comment_id=parent_comment_id,
        comment=body,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {
        'message': 'Comment added successfully',
        'comment': row,
    }


def update_story_partial(
    db: Session,
    story_id: int,
    requester_id: int,
    requester_role: str,
    updates: dict[str, Any],
) -> Story:
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='No fields to update',
        )

    story = db.query(Story).filter(Story.id == story_id).first()
    if not story:
        raise HTTPException(status_code=404, detail='Story not found')

    is_admin = requester_role == 'admin'
    if story.user_id != requester_id and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Not authorized to update this story',
        )

    if 'title' in updates:
        story.title = str(updates['title'])[:500].strip()

    if 'description' in updates:
        story.description = updates['description']

    if 'location' in updates:
        loc = updates['location']
        if loc is None or (isinstance(loc, str) and not str(loc).strip()):
            story.location = None
        else:
            story.location = str(loc).strip()[:500]

    if 'image' in updates:
        story.image = str(updates['image']).strip()[:20_000]

    if 'tags' in updates:
        tag_source = updates['tags']
        display_tags = _dedupe_tag_strings(
            None if tag_source is None else list(tag_source),
        )
        story.tag_links.clear()
        for t in display_tags:
            story.tag_links.append(_get_or_create_tag(db, t))
        story.tags = [t for t in display_tags] if display_tags else None
        db.flush()

    story.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(story)
    return story


def delete_story(
    db: Session,
    story_id: int,
    requester_id: int,
    requester_role: str,
) -> None:
    story = db.query(Story).filter(Story.id == story_id).first()
    if not story:
        raise HTTPException(status_code=404, detail='Story not found')
    is_admin = requester_role == 'admin'
    if story.user_id != requester_id and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Not authorized to delete this story',
        )
    db.delete(story)
    db.commit()
