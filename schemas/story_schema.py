import json
import re
from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Example for OpenAPI (description must be >= 500 characters for the real API)
_STORY_DESC_SAMPLE = (
    'This is a sample travel story body used for documentation. '
    * 15
)[:520]


STORY_OPENAPI_JSON_EXAMPLE: dict[str, Any] = {
    'title': 'My travel story',
    'description': _STORY_DESC_SAMPLE,
    'image': 'https://example.com/image.jpg',
    'location': 'Goa',
    'tags': ['travel', 'beach'],
}


class StoryCreateFromJson(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(..., min_length=1, max_length=500, description='Story title')
    description: str = Field(
        ...,
        min_length=500,
        description='Description must be at least 500 characters',
    )
    location: Optional[str] = Field(default=None, max_length=500)
    tags: Optional[list[str]] = None
    image: str = Field(..., min_length=1, description='Image URL (http or https)')

    @field_validator('image')
    @classmethod
    def image_must_be_url(cls, v: str) -> str:
        t = v.strip()
        if not re.match(r'https?://', t, re.I):
            raise ValueError('Image must be a valid http or https URL')
        return t

    @field_validator('tags', mode='before')
    @classmethod
    def empty_tags_to_none(cls, v):
        if v is None:
            return None
        if isinstance(v, list) and len(v) == 0:
            return None
        return v

    @field_validator('tags')
    @classmethod
    def each_tag_str(cls, v: Optional[list]) -> Optional[list[str]]:
        if v is None:
            return None
        out: list[str] = []
        for item in v:
            if not isinstance(item, str):
                raise ValueError('Each tag must be a string')
            s = item.strip()
            if s:
                out.append(s)
        if not out:
            return None
        return out


class StoryItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    title: str
    description: str
    location: Optional[str] = None
    image: str
    tags: Optional[list[str]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class StoryByIdResponse(BaseModel):
    title: str
    image: str
    description: str
    tags: Optional[list[str]] = None
    location: Optional[str] = None


class StoryPatchJson(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None
    tags: Optional[list[str]] = None
    image: Optional[str] = Field(
        default=None, description='https URL when sending JSON, or set via multipart file/file_url',
    )

    @field_validator('title')
    @classmethod
    def title_if_provided(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        t = (v or '').strip()
        if not t:
            raise ValueError('title must not be empty when provided')
        return t[:500]

    @field_validator('description')
    @classmethod
    def description_min_if_provided(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        if len(v.strip()) < 500:
            raise ValueError('Description must be at least 500 characters when provided')
        return v

    @field_validator('location', mode='before')
    @classmethod
    def empty_location_to_none(cls, v):
        if v is None:
            return None
        if isinstance(v, str) and not v.strip():
            return None
        return v

    @field_validator('location')
    @classmethod
    def location_max(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        return v.strip()[:500]

    @field_validator('image')
    @classmethod
    def image_url_if_provided(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        t = str(v).strip()[:20_000]
        if not t:
            return None
        if re.match(r'https?://', t, re.I):
            return t
        if t.startswith('/'):
            return t
        raise ValueError('Image must be a valid http(s) URL or a public path starting with /')

    @field_validator('tags', mode='before')
    @classmethod
    def tags_before(cls, v):
        if v is None:
            return None
        return v

    @field_validator('tags')
    @classmethod
    def each_tag_str(cls, v: Optional[list]) -> Optional[list[str]]:
        if v is None:
            return None
        if not isinstance(v, list):
            raise ValueError('tags must be an array of strings')
        out: list[str] = []
        for item in v:
            if not isinstance(item, str):
                raise ValueError('Each tag must be a string')
            s = item.strip()
            if s:
                out.append(s)
        return out or []


class StoryPatchResponse(BaseModel):
    message: str = 'Story updated successfully'
    story: StoryItemResponse


class AllStoriesV1User(BaseModel):
    firstname: str
    lastname: str
    facebook: Optional[str] = None
    twitter: Optional[str] = None
    linkedin: Optional[str] = None
    instagram: Optional[str] = None
    youtube: Optional[str] = None
    about_author: Optional[str] = None
    profession: Optional[str] = None


class AllStoriesV1Item(BaseModel):
    id: int
    user_id: int
    image: str
    title: str
    description: str
    location: Optional[str] = None
    tags: Optional[list[str]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    user: AllStoriesV1User
    total_likes: int
    total_dislikes: int


class StoryCreatedResponse(BaseModel):
    message: str = 'Story created successfully'
    story: StoryItemResponse


class StoryReactRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    story_id: int = Field(..., ge=1)
    reaction_type: Literal['like', 'dislike']


class StoryReactResponse(BaseModel):
    message: str
    total_likes: int
    total_dislikes: int


class StoryCommentRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    story_id: int = Field(..., ge=1)
    comment: str = Field(..., min_length=1)
    parent_comment_id: Optional[int] = Field(default=None, ge=1)


class StoryCommentItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    story_id: int
    user_id: int
    parent_comment_id: Optional[int] = None
    comment: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class StoryCommentCreatedResponse(BaseModel):
    message: str = 'Comment added successfully'
    comment: StoryCommentItemResponse


def get_post_stories_openapi_extra() -> dict[str, Any]:
    """
    Request body for POST /stories (JSON). Multipart is documented on POST /stories/upload.
    """
    json_schema = StoryCreateFromJson.model_json_schema()
    return {
        'requestBody': {
            'description': (
                'JSON only. Send the **image** as a public **https** URL. '
                'To upload a file, use **POST /stories/upload** with `multipart/form-data` (file or file_url).'
            ),
            'required': True,
            'content': {
                'application/json': {
                    'schema': json_schema,
                    'example': STORY_OPENAPI_JSON_EXAMPLE,
                }
            },
        }
    }


# Used by POST /stories/upload: Swagger shows tags as a string array (Add item per value).
TAGS_MULTIPART_FORM_DESCRIPTION = (
    'Zero or more tag values. **Add item** in Swagger to send multiple `tags` fields, '
    'or use a single value. **Each** value can be: one tag (`beach`); several tags '
    'separated by commas (`travel, hiking`); or a JSON string of an array ('
    '`["travel","hiking"]`). Values are trimmed, lowercased, and de-duplicated. '
    'Omit or leave all empty to create a story with no tags.'
)


def _parse_flexible_tag_segment(segment: str) -> list[str]:
    """
    Parse a single form value into zero or more raw tag strings (before global normalize).
    """
    t = (segment or '').strip()
    if not t:
        return []
    if t.startswith('['):
        try:
            data = json.loads(t)
        except json.JSONDecodeError as exc:
            raise ValueError(
                'tags: invalid JSON. Use a valid array like [\"travel\",\"hiking\"], '
                'or use plain text / comma-separated tags without [ ].'
            ) from exc
        if not isinstance(data, list):
            raise ValueError(
                'When using JSON, tags must be a JSON array of strings, e.g. [\"travel\",\"hiking\"].'
            )
        out: list[str] = []
        for item in data:
            if not isinstance(item, str):
                raise ValueError('Each tag in a JSON array must be a string.')
            s = item.strip()
            if s:
                out.append(s)
        return out
    if ',' in t:
        return [p.strip() for p in t.split(',') if p and p.strip()]
    return [t]


def normalize_multipart_tag_inputs(values: list[str] | None) -> Optional[list[str]]:
    """
    Flattens all supported multipart tag input shapes into a single normalized list:
    trim, lowercase, de-duplicate, preserve first-seen order.
    """
    if not values:
        return None
    raw: list[str] = []
    for segment in values:
        if segment is None or not str(segment).strip():
            continue
        raw.extend(_parse_flexible_tag_segment(str(segment)))
    if not raw:
        return None
    seen: set[str] = set()
    out: list[str] = []
    for s in raw:
        st = s.strip()
        if not st:
            continue
        k = st.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(k)
    return out if out else None
