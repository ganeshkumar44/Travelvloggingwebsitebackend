import os
import re
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from auth.auth_handler import verify_token
from database import get_db
from controllers.story_controller import (
    STORY_IMAGE_MAX_BYTES,
    add_story_comment,
    create_story_record,
    get_user_id_by_email,
    react_to_story,
    save_uploaded_story_image_bytes,
)
from schemas.story_schema import (
    TAGS_MULTIPART_FORM_DESCRIPTION,
    StoryCommentCreatedResponse,
    StoryCommentRequest,
    StoryCreateFromJson,
    StoryCreatedResponse,
    StoryReactRequest,
    StoryReactResponse,
    get_post_stories_openapi_extra,
    normalize_multipart_tag_inputs,
)

router = APIRouter(tags=['Stories'])

UPLOAD_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'uploads',
)


def get_current_user_id(
    current_user_email: str = Depends(verify_token),
    db: Session = Depends(get_db),
) -> int:
    """
    JWT in Authorization: Bearer <access_token> (set Swagger 'Authorize' with token from /login or /loginform).
    The user's id is always taken from this token, never from the request body.
    """
    return get_user_id_by_email(db, current_user_email)


@router.post(
    '/stories/react',
    response_model=StoryReactResponse,
    summary='Like or dislike a story',
    description=(
        '**Authorize** with Bearer token. '
        'Body: `story_id` and `reaction_type` (`"like"` or `"dislike"`). '
        'The user is taken from the token only, not the body. '
        'If you repeat the same reaction, it is removed (toggle). '
        'A different reaction switches the vote.'
    ),
)
def post_story_reaction(
    body: StoryReactRequest,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
):
    return react_to_story(
        db=db,
        user_id=current_user_id,
        story_id=body.story_id,
        reaction_type=body.reaction_type,
    )


@router.post(
    '/stories/comment',
    response_model=StoryCommentCreatedResponse,
    summary='Add a comment on a story',
    description=(
        '**Authorize** with Bearer token. '
        'Body: `story_id` and `comment` (user from token only). '
        'Optional `parent_comment_id` to reply to an existing comment (must be on the same story).'
    ),
)
def post_story_comment(
    body: StoryCommentRequest,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
):
    return add_story_comment(
        db=db,
        user_id=current_user_id,
        story_id=body.story_id,
        comment=body.comment,
        parent_comment_id=body.parent_comment_id,
    )


def _validate_file_url(href: str) -> str:
    t = href.strip()
    if not re.match(r'https?://', t, re.I):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='file_url must be a valid http or https URL',
        )
    return t


# --- JSON: body is parsed by FastAPI; Depends(verify_token) still receives the Authorization header ---


@router.post(
    '/stories',
    response_model=StoryCreatedResponse,
    summary='Create a new story (JSON body)',
    description=(
        'Send `application/json` with an `image` URL. '
        '**Authorize** with a Bearer token first. '
        'For `multipart/form-data` (file or `file_url`), use **POST /stories/upload**.\n\n'
        '**cURL (JSON):** `curl -X POST "http://localhost:8000/stories" '
        '-H "Authorization: Bearer TOKEN" -H "Content-Type: application/json" '
        '-d \'{"title":"My story","description":"<min 500 chars...>","image":"https://...","tags":["a"]}\'`'
    ),
    openapi_extra=get_post_stories_openapi_extra(),
)
def add_story_json(
    body: StoryCreateFromJson,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
):
    story = create_story_record(
        db=db,
        user_id=current_user_id,
        title=body.title.strip()[:500],
        description=body.description,
        location=body.location.strip()[:500]
        if body.location and body.location.strip()
        else None,
        image_url=body.image.strip(),
        tag_strings=body.tags,
    )
    return StoryCreatedResponse(
        message='Story created successfully',
        story=story,
    )


# --- Multipart: Form() + File() so Swagger shows fields and the Bearer flow matches JSON routes ---


@router.post(
    '/stories/upload',
    response_model=StoryCreatedResponse,
    summary='Create a new story (multipart / file or URL)',
    description=(
        '`multipart/form-data` with `title` and `description` (min 500 chars). '
        'Provide **either** `file` (binary upload) **or** `file_url` (https link), not both required, '
        'but if `file` is sent and has content, it is preferred over `file_url`.\n\n'
        '**Tags:** add multiple `tags` entries in Swagger (Add item), or one value per string format '
        '(see the **tags** field description on this form). '
        'Single value, comma-separated, JSON array, or several form fields are all supported.\n\n'
        '**cURL (multipart, file):**\n```\n'
        'curl -X POST "http://localhost:8000/stories/upload" \\\n'
        '  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \\\n'
        "  -F 'title=My story' \\\n"
        "  -F 'description=MIN500CHARS...' \\\n"
        "  -F 'file=@/path/to/photo.jpg'\n```\n\n"
        '**cURL (multipart, URL instead of file):**\n```\n'
        'curl -X POST "http://localhost:8000/stories/upload" \\\n'
        '  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \\\n'
        "  -F 'title=My story' \\\n"
        "  -F 'description=MIN500CHARS...' \\\n"
        "  -F 'file_url=https://example.com/p.jpg'\n```"
    ),
)
async def add_story_multipart(
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
    title: str = Form(..., description='Story title'),
    description: str = Form(
        ...,
        description='At least 500 characters',
    ),
    location: Optional[str] = Form(
        default=None,
        description='Optional location',
    ),
    tags: list[str] = Form(
        default_factory=list,
        description=TAGS_MULTIPART_FORM_DESCRIPTION,
    ),
    file: Optional[UploadFile] = File(
        default=None,
        description='Image file (jpeg, png, gif, webp; max 10MB). Use this or file_url.',
    ),
    file_url: Optional[str] = Form(
        default=None,
        description='https URL to an image. Use this if not uploading a file.',
    ),
):
    title_s = (title or '').strip()[:500]
    if not title_s:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='title is required',
        )
    desc_s = description or ''
    if len(desc_s.strip()) < 500:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Description must be at least 500 characters',
        )

    loc_val: Optional[str] = None
    if location and str(location).strip():
        loc_val = str(location).strip()[:500]

    try:
        tag_list = normalize_multipart_tag_inputs(tags)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e

    if file is not None:
        file_body = await file.read()
    else:
        file_body = b''

    if file_body and len(file_body) > 0:
        if len(file_body) > STORY_IMAGE_MAX_BYTES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Image file is too large',
            )
        public_url = save_uploaded_story_image_bytes(
            body=file_body,
            content_type=file.content_type,
            storage_root=UPLOAD_ROOT,
        )
    elif file_url and str(file_url).strip():
        public_url = _validate_file_url(str(file_url))
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Provide a file in field "file" or an https URL in "file_url".',
        )

    story = create_story_record(
        db=db,
        user_id=current_user_id,
        title=title_s,
        description=desc_s,
        location=loc_val,
        image_url=public_url,
        tag_strings=tag_list,
    )
    return StoryCreatedResponse(
        message='Story created successfully',
        story=story,
    )
