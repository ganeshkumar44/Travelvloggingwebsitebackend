from sqlalchemy import Column, Integer, String, Boolean, TIMESTAMP, Text, text
from database import Base

class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, index=True)
    firstname = Column(String(100), nullable=False)
    lastname = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, nullable=False)
    phone = Column(String(20))
    password = Column(String(255), nullable=False)
    gender = Column(String(20))
    about_author = Column(Text, nullable=True)
    profession = Column(String(150), nullable=True)
    role = Column(String(50), default='user')
    is_verified = Column(Boolean, default=False)
    forget_password_code = Column(String(10), nullable=True)
    forget_password_code_expires = Column(TIMESTAMP, nullable=True)
    firsttime_register_code = Column(String(6), nullable=True)
    created_at = Column(TIMESTAMP, server_default=text('CURRENT_TIMESTAMP'))
    updated_at = Column(TIMESTAMP, server_default=text('CURRENT_TIMESTAMP'))