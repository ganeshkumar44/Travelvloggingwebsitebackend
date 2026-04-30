import os
import uuid
from typing import Optional
from urllib.parse import quote

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import HTTPException, status

STORY_IMAGE_MAX_BYTES = 10 * 1024 * 1024
IMAGE_TYPES_TO_EXT = {
    'image/jpeg': '.jpg',
    'image/jpg': '.jpg',
    'image/png': '.png',
    'image/gif': '.gif',
    'image/webp': '.webp',
}


def upload_story_image_bytes_to_s3(body: bytes, content_type: Optional[str]) -> str:
    """
    Validate image bytes (same rules as local save_uploaded_story_image_bytes),
    upload to S3 under stories/<uuid>.<ext>, return public HTTPS URL.
    """
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
    key = f'stories/{name}'

    access_key = os.getenv('AWS_ACCESS_KEY_ID')
    secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
    region = os.getenv('AWS_REGION')
    bucket = os.getenv('AWS_BUCKET_NAME')
    if not access_key or not secret_key or not region or not bucket:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail='Image storage is not configured',
        )

    client = boto3.client(
        's3',
        region_name=region.strip(),
        aws_access_key_id=access_key.strip(),
        aws_secret_access_key=secret_key.strip(),
    )
    try:
        client.put_object(
            Bucket=bucket.strip(),
            Key=key,
            Body=body,
            ContentType=raw,
        )
    except ClientError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail='Could not upload image to storage. Please try again later.',
        ) from None
    except BotoCoreError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail='Could not upload image to storage. Please try again later.',
        ) from None

    safe_key = quote(key, safe='/')
    return f'https://{bucket.strip()}.s3.{region.strip()}.amazonaws.com/{safe_key}'
