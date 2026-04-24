from sqlalchemy import Column, ForeignKey, Integer, String, Table, Text, TIMESTAMP, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import relationship

from database import Base

story_tags = Table(
    'story_tags',
    Base.metadata,
    Column('story_id', Integer, ForeignKey('stories.id', ondelete='CASCADE'), primary_key=True),
    Column('tag_id', Integer, ForeignKey('tags.id', ondelete='CASCADE'), primary_key=True),
)


class Tag(Base):
    __tablename__ = 'tags'

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    stories = relationship('Story', secondary=story_tags, back_populates='tag_links')


class Story(Base):
    __tablename__ = 'stories'

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=False)
    location = Column(String(500), nullable=True)
    image = Column(Text, nullable=False)
    tags = Column(ARRAY(String), nullable=True)
    created_at = Column(TIMESTAMP, server_default=text('CURRENT_TIMESTAMP'))
    updated_at = Column(TIMESTAMP, server_default=text('CURRENT_TIMESTAMP'))
    tag_links = relationship('Tag', secondary=story_tags, back_populates='stories')
