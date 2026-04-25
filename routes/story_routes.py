import os
import re
from typing import Annotated, Any, Optional

from fastapi import (
    APIRouter,
    Body,
    Depends,
    File,
    Form,
    HTTPException,
    Path,
    UploadFile,
    status,
)
from pydantic import ValidationError
from sqlalchemy.orm import Session

from auth.auth_handler import verify_token
from database import get_db
from controllers.story_controller import (
    STORY_IMAGE_MAX_BYTES,
    add_story_comment,
    create_story_record,
    get_all_stories,
    get_all_stories_v1,
    get_story_by_id,
    get_user_id_and_role_by_email,
    get_user_id_by_email,
    react_to_story,
    save_uploaded_story_image_bytes,
    update_story_partial,
)
from schemas.story_schema import (
    TAGS_MULTIPART_FORM_DESCRIPTION,
    AllStoriesV1Item,
    StoryByIdResponse,
    StoryCommentCreatedResponse,
    StoryCommentRequest,
    StoryCreateFromJson,
    StoryCreatedResponse,
    StoryItemResponse,
    StoryPatchJson,
    StoryPatchResponse,
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


def _run_story_patch(
    raw: dict[str, Any],
    story_id: int,
    requester_id: int,
    requester_role: str,
    db: Session,
) -> StoryPatchResponse:
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='No fields to update',
        )
    try:
        p = StoryPatchJson.model_validate(raw)
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.errors(),
        ) from e
    updates = p.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='No fields to update',
        )
    story = update_story_partial(
        db=db,
        story_id=story_id,
        requester_id=requester_id,
        requester_role=requester_role,
        updates=updates,
    )
    return StoryPatchResponse(
        message='Story updated successfully',
        story=story,
    )


@router.get(
    '/all-stories',
    response_model=list[StoryItemResponse],
    summary='Fetch all stories',
)
def fetch_all_stories(db: Session = Depends(get_db)):
    return get_all_stories(db)


@router.get(
    '/v1/all-stories',
    response_model=list[AllStoriesV1Item],
    summary='Fetch all stories (full detail, author, like/dislike counts)',
    description=(
        'Returns every story with core fields, nested author profile fields, '
        'and aggregated `total_likes` / `total_dislikes` from `story_reactions`.'
    ),
)
def fetch_all_stories_v1_endpoint(db: Session = Depends(get_db)):
    return get_all_stories_v1(db)


@router.get(
    '/v1/stories/{story_id}',
    response_model=StoryByIdResponse,
    summary='Fetch a single story by id',
)
def fetch_story_by_id(
    story_id: Annotated[int, Path(ge=1, description='Story id')],
    db: Session = Depends(get_db),
):
    story = get_story_by_id(db, story_id)
    return {
        'title': story.title,
        'image': story.image,
        'description': story.description,
        'tags': story.tags,
        'location': story.location,
    }


@router.patch(
    '/v1/stories/{story_id}/upload',
    response_model=StoryPatchResponse,
    summary='Update a story (multipart / file or image URL, same as POST /stories/upload)',
    description=(
        '`multipart/form-data` only. **Authorize** with Bearer token. '
        '**Story author** or **admin** can update. All fields are **optional**  omit what you do not want to change. '
        'Provide **either** `file` (binary) **or** `file_url` (https) to change the image, or leave both out to keep the current image. '
        '**Tags** support the same flexible formats as **POST /stories/upload**; omit the `tags` form parts entirely to leave existing tags. '
        'For a JSON request body, use **PATCH** `/v1/stories/{story_id}` (application/json).'
    ),
)
async def patch_story_v1_multipart(
    story_id: Annotated[int, Path(ge=1, description='Story id')],
    db: Session = Depends(get_db),
    current_user_email: str = Depends(verify_token),
    title: Optional[str] = Form(
        default=None,
        description='New title, or omit to leave unchanged',
    ),
    description: Optional[str] = Form(
        default=None,
        description='New description, or omit; min 500 characters if you send a new description',
    ),
    location: Optional[str] = Form(
        default=None,
        description='New location, or omit to leave unchanged. Send an empty value to clear.',
    ),
    tags: list[str] = Form(
        default_factory=list,
        description=TAGS_MULTIPART_FORM_DESCRIPTION,
    ),
    file: Optional[UploadFile] = File(
        default=None,
        description='Image file (jpeg, png, gif, webp; max 10MB). If present (with a filename and bytes), it overrides `file_url` for the new image path.',
    ),
    file_url: Optional[str] = Form(
        default=None,
        description='https URL to a new image. Use if not uploading a file. Both may be omitted to keep the existing image.',
    ),
):
    requester_id, requester_role = get_user_id_and_role_by_email(
        db, current_user_email
    )
    raw: dict[str, Any] = {}
    if title is not None:
        raw['title'] = str(title)
    if description is not None:
        raw['description'] = str(description)
    if location is not None:
        t = str(location)
        raw['location'] = t.strip() if t and t.strip() else None
    if tags:
        try:
            ntags = normalize_multipart_tag_inputs(tags)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
            ) from e
        if ntags is not None:
            raw['tags'] = ntags

    file_body = b''
    if file is not None and isinstance(file, UploadFile) and file.filename and str(
        file.filename
    ).strip():
        file_body = await file.read() or b''
    if file_body and len(file_body) > 0:
        if len(file_body) > STORY_IMAGE_MAX_BYTES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Image file is too large',
            )
        raw['image'] = save_uploaded_story_image_bytes(
            body=file_body,
            content_type=file.content_type,
            storage_root=UPLOAD_ROOT,
        )
    elif file_url and str(file_url).strip():
        raw['image'] = _validate_file_url(str(file_url).strip())

    return _run_story_patch(
        raw, story_id, requester_id, requester_role, db
    )


@router.patch(
    '/v1/stories/{story_id}',
    response_model=StoryPatchResponse,
    summary='Update a story (JSON / application/json)',
    description=(
        '**Content-Type: application/json** only. **Authorize** with Bearer token. '
        '**Story author** or **admin** can update. Send any combination of `title`, `description`, `location`, `tags`, `image` (URL). '
        'For `multipart/form-data` with `file` / `file_url`, use **PATCH** `/v1/stories/{story_id}/upload` (same fields as **POST** `/stories/upload`).'
    ),
)
def patch_story_v1_json(
    story_id: Annotated[int, Path(ge=1, description='Story id')],
    body: StoryPatchJson = Body(
        ...,
        description='Field-level optional partial update. Omit a property in JSON to leave it unchanged.',
    ),
    db: Session = Depends(get_db),
    current_user_email: str = Depends(verify_token),
):
    requester_id, requester_role = get_user_id_and_role_by_email(
        db, current_user_email
    )
    raw = body.model_dump(exclude_unset=True, exclude_none=False)
    return _run_story_patch(
        raw, story_id, requester_id, requester_role, db
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
