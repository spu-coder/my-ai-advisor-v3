"""
Database Module - Async SQLAlchemy 2.0 with PostgreSQL
=======================================================
This module provides async database connection and models using SQLAlchemy 2.0
with asyncpg driver for PostgreSQL. SQLite is strictly forbidden.

وحدة قاعدة البيانات - SQLAlchemy 2.0 غير المتزامن مع PostgreSQL
================================================================
توفر هذه الوحدة اتصال قاعدة بيانات غير متزامن ونماذج باستخدام SQLAlchemy 2.0
مع سائق asyncpg لـ PostgreSQL. SQLite محظور تماماً.
"""

import os
from datetime import datetime
from typing import AsyncGenerator
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean, Text, JSON
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker, AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, relationship, declared_attr

# ------------------------------------------------------------
# إعداد اتصال قاعدة البيانات - Async PostgreSQL Only
# ------------------------------------------------------------
DEFAULT_DATABASE_URL = "postgresql+asyncpg://advisor:advisor@postgres:5432/advisor_db"
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)

# التحقق من أن الاتصال هو PostgreSQL وليس SQLite
if DATABASE_URL.startswith("sqlite"):
    raise RuntimeError(
        "SQLite is strictly forbidden. Use PostgreSQL with asyncpg driver. "
        "SQLite محظور تماماً. استخدم PostgreSQL مع سائق asyncpg."
    )

# التحقق من أن الاتصال يستخدم asyncpg
if not DATABASE_URL.startswith("postgresql+asyncpg://"):
    # محاولة تحويل postgresql:// أو postgresql+psycopg:// إلى postgresql+asyncpg://
    if DATABASE_URL.startswith("postgresql+psycopg://"):
        DATABASE_URL = DATABASE_URL.replace("postgresql+psycopg://", "postgresql+asyncpg://")
    elif DATABASE_URL.startswith("postgresql://"):
        DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
    else:
        raise RuntimeError(
            f"Invalid database URL format. Must use postgresql+asyncpg://. "
            f"Received: {DATABASE_URL[:30]}..."
        )

# إنشاء محرك قاعدة البيانات غير المتزامن
ENGINE = create_async_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    echo=False,  # ضبط على True للتطوير لرؤية استعلامات SQL
)

# Base class للنماذج - Async Compatible
class Base(AsyncAttrs, DeclarativeBase):
    """Base class for all database models with async support"""
    pass

# ------------------------------------------------------------
# نماذج قاعدة البيانات
# ------------------------------------------------------------

class User(Base):
    """نموذج المستخدم - Users Table"""
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, unique=True, index=True)  # معرف الطالب/المستخدم (الرقم الجامعي)
    full_name = Column(String)
    hashed_password = Column(String)  # حقل كلمة المرور المشفرة (كلمة سر النظام الجامعي)
    role = Column(String, default="student")  # طالب، إداري
    email = Column(String, unique=True, nullable=True)  # أصبح اختياري
    university_password = Column(String, nullable=True)  # كلمة سر النظام الجامعي (مشفرة)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_data_sync = Column(DateTime, nullable=True)  # آخر مرة تم فيها جمع البيانات من النظام الجامعي

    # Relationships
    progress_records = relationship("ProgressRecord", back_populates="user", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    chat_messages = relationship("ChatMessage", back_populates="user", cascade="all, delete-orphan")

class ProgressRecord(Base):
    """نموذج سجل التقدم - Progress Records Table"""
    __tablename__ = "progress_records"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.user_id"), index=True)
    course_code = Column(String)
    grade = Column(String)
    hours = Column(Integer)
    semester = Column(String)
    course_name = Column(String, nullable=True)  # اسم المقرر
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    user = relationship("User", back_populates="progress_records")

class StudentAcademicInfo(Base):
    """معلومات أكاديمية شاملة للطالب من النظام الجامعي"""
    __tablename__ = "student_academic_info"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True, unique=True)  # الرقم الجامعي
    gpa = Column(Float, nullable=True)  # المعدل التراكمي
    total_hours = Column(Integer, nullable=True)  # إجمالي الساعات المطلوبة
    completed_hours = Column(Integer, nullable=True)  # الساعات المكتملة
    remaining_hours = Column(Integer, nullable=True)  # الساعات المتبقية
    academic_status = Column(String, nullable=True)  # الحالة الأكاديمية
    current_semester = Column(String, nullable=True)  # الفصل الحالي
    raw_data = Column(JSON, nullable=True)  # البيانات الخام من النظام الجامعي
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class RemainingCourse(Base):
    """المقررات المتبقية للتسجيل"""
    __tablename__ = "remaining_courses"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)
    course_code = Column(String, index=True)
    course_name = Column(String, nullable=True)
    hours = Column(Integer, nullable=True)
    prerequisites = Column(String, nullable=True)  # المتطلبات السابقة
    semester = Column(String, nullable=True)  # الفصل المقترح
    raw_data = Column(JSON, nullable=True)  # البيانات الخام
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Notification(Base):
    """نموذج الإشعارات - Notifications Table"""
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.user_id"), index=True)
    message = Column(String)
    type = Column(String)  # تنبيه، إشعار، توصية
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationship
    user = relationship("User", back_populates="notifications")

class ChatMessage(Base):
    """سجل رسائل الدردشة للحفاظ على السياق"""
    __tablename__ = "chat_messages"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.user_id"), index=True)
    role = Column(String)  # user / assistant
    content = Column(Text)
    intent = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationship
    user = relationship("User", back_populates="chat_messages")

# ------------------------------------------------------------
# Async Session Management
# ------------------------------------------------------------

# إنشاء AsyncSessionLocal
AsyncSessionLocal = async_sessionmaker(
    ENGINE,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency function to get async database session.
    / دالة اعتمادية للحصول على جلسة قاعدة بيانات غير متزامنة.
    
    Usage:
        @app.get("/items")
        async def read_items(db: AsyncSession = Depends(get_db)):
            result = await db.execute(select(Item))
            return result.scalars().all()
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

# ------------------------------------------------------------
# وظائف التهيئة
# ------------------------------------------------------------

async def init_db():
    """
    Initialize database - create all tables.
    / تهيئة قاعدة البيانات - إنشاء جميع الجداول.
    
    Note: This should be called during application startup.
    / ملاحظة: يجب استدعاء هذه الدالة عند بدء التطبيق.
    """
    async with ENGINE.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# دوال التوافق مع الكود القديم (للانتقال التدريجي)
async def get_users_session() -> AsyncGenerator[AsyncSession, None]:
    """دالة للحصول على جلسة قاعدة البيانات (للتوافق)"""
    async for session in get_db():
        yield session

async def get_progress_session() -> AsyncGenerator[AsyncSession, None]:
    """دالة للحصول على جلسة قاعدة البيانات (للتوافق)"""
    async for session in get_db():
        yield session

async def get_notifications_session() -> AsyncGenerator[AsyncSession, None]:
    """دالة للحصول على جلسة قاعدة البيانات (للتوافق)"""
    async for session in get_db():
        yield session
