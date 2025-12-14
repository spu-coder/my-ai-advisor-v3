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
    
    # Learning Style Fields (FSLSM Enhancement)
    # حقول أسلوب التعلم (تحسين FSLSM)
    fslsm_profile = Column(JSON, nullable=True)  # {"processing": "active", "perception": "sensing", "input": "visual", "understanding": "sequential"}
    fslsm_confidence = Column(Float, nullable=True)  # Confidence score for ML prediction (0-1)
    fslsm_predicted_at = Column(DateTime, nullable=True)  # When FSLSM was predicted
    behavioral_baseline = Column(JSON, nullable=True)  # Baseline behavioral data for deviation detection

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

class FAQEntry(Base):
    """
    FAQ Entry Model - Unified RAG (URAG) System
    نموذج سؤال شائع - نظام URAG (Unified RAG)
    
    Stores exact factual answers for 100% accuracy
    يخزن إجابات دقيقة 100% للأسئلة الواقعية
    """
    __tablename__ = "faq_entries"
    id = Column(Integer, primary_key=True, index=True)
    question_pattern = Column(String, nullable=False, index=True)  # Regex pattern for matching
    answer_template = Column(Text, nullable=False)  # Exact answer template
    category = Column(String, nullable=False, index=True)  # regulations, fees, deadlines, etc.
    priority = Column(Integer, default=1)  # For ordering (higher = more important)
    metadata = Column(JSON, nullable=True)  # department, year, status, etc.
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True, index=True)  # Enable/disable FAQ entry

class FAQMatchLog(Base):
    """
    FAQ Match Log - Analytics for URAG System
    سجل مطابقة الأسئلة الشائعة - تحليلات لنظام URAG
    
    Tracks FAQ matches for analytics and improvement
    يتتبع مطابقات الأسئلة الشائعة للتحليلات والتحسين
    """
    __tablename__ = "faq_match_logs"
    id = Column(Integer, primary_key=True, index=True)
    user_query = Column(Text, nullable=False)  # Original user query
    matched_faq_id = Column(Integer, ForeignKey("faq_entries.id"), nullable=True, index=True)
    confidence_score = Column(Float, nullable=True)  # Match confidence (0-1)
    used_llm_fallback = Column(Boolean, default=False)  # Whether RAG was used as fallback
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationship
    faq_entry = relationship("FAQEntry", foreign_keys=[matched_faq_id])

class AdvisorAlert(Base):
    """
    Advisor Alert Model - Advisor-in-the-Loop System
    نموذج تنبيه المرشد - نظام المرشد-في-الحلقة
    
    Stores alerts generated from predictions for advisor review
    يخزن التنبيهات المولدة من التنبؤات لمراجعة المرشد
    """
    __tablename__ = "advisor_alerts"
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(String, ForeignKey("users.user_id"), nullable=False, index=True)
    alert_type = Column(String, nullable=False, index=True)  # academic_risk, wellness_concern, behavioral_change
    risk_level = Column(String, nullable=False, index=True)  # low, medium, high, critical
    description = Column(Text, nullable=False)  # Human-readable description
    
    # Feature Importance (for transparency)
    # أهمية الميزات (للشفافية)
    contributing_factors = Column(JSON, nullable=True)  # {"low_attendance": 0.4, "poor_prereq_grade": 0.3, ...}
    
    prediction_confidence = Column(Float, nullable=True)  # Prediction confidence (0-1)
    
    # Advisor action fields
    # حقول إجراء المرشد
    advisor_id = Column(String, ForeignKey("users.user_id"), nullable=True, index=True)  # Assigned advisor
    status = Column(String, default="pending", index=True)  # pending, reviewed, actioned, dismissed
    advisor_notes = Column(Text, nullable=True)  # Advisor's notes/actions taken
    actioned_at = Column(DateTime, nullable=True)  # When advisor took action
    
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    student = relationship("User", foreign_keys=[student_id], backref="student_alerts")
    advisor = relationship("User", foreign_keys=[advisor_id], backref="advisor_alerts")

class Intervention(Base):
    """
    Intervention Model - Records advisor actions
    نموذج التدخل - يسجل إجراءات المرشد
    
    Tracks interventions taken by advisors in response to alerts
    يتتبع التدخلات التي يتخذها المرشدون استجابة للتنبيهات
    """
    __tablename__ = "interventions"
    id = Column(Integer, primary_key=True, index=True)
    alert_id = Column(Integer, ForeignKey("advisor_alerts.id"), nullable=False, index=True)
    intervention_type = Column(String, nullable=False)  # email, meeting, resource_suggestion, etc.
    description = Column(Text, nullable=False)  # Description of intervention
    scheduled_at = Column(DateTime, nullable=True)  # When intervention is scheduled
    completed_at = Column(DateTime, nullable=True)  # When intervention was completed
    effectiveness_rating = Column(Integer, nullable=True)  # 1-5 rating from student feedback
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    alert = relationship("AdvisorAlert", backref="interventions")

class WellnessMetric(Base):
    """
    Wellness Metric Model - Behavioral tracking for wellness monitoring
    نموذج مقياس العافية - تتبع سلوكي لمراقبة العافية
    
    Tracks individual behavioral metrics for wellness analysis
    يتتبع المقاييس السلوكية الفردية لتحليل العافية
    """
    __tablename__ = "wellness_metrics"
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(String, ForeignKey("users.user_id"), nullable=False, index=True)
    metric_type = Column(String, nullable=False, index=True)  # login_pattern, session_duration, late_submissions, etc.
    metric_value = Column(Float, nullable=False)  # Current metric value
    baseline_value = Column(Float, nullable=True)  # Baseline value for deviation detection
    deviation_percentage = Column(Float, nullable=True)  # Percentage deviation from baseline
    recorded_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationship
    student = relationship("User", foreign_keys=[student_id], backref="wellness_metrics")

class WellnessAlert(Base):
    """
    Wellness Alert Model - Proactive wellness monitoring alerts
    نموذج تنبيه العافية - تنبيهات مراقبة العافية الاستباقية
    
    Stores wellness alerts generated from behavioral pattern analysis
    يخزن تنبيهات العافية المولدة من تحليل الأنماط السلوكية
    """
    __tablename__ = "wellness_alerts"
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(String, ForeignKey("users.user_id"), nullable=False, index=True)
    alert_level = Column(String, nullable=False, index=True)  # info, warning, critical
    indicators = Column(JSON, nullable=True)  # List of detected indicators
    wellness_score = Column(Float, nullable=False)  # Overall wellness score (0-1)
    recommended_intervention = Column(Text, nullable=True)  # Recommended intervention level
    opt_in_status = Column(Boolean, default=True)  # Student consent for wellness monitoring
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    student = relationship("User", foreign_keys=[student_id], backref="wellness_alerts")

class LearningInteraction(Base):
    """
    Learning Interaction Model - Tracks student learning behaviors
    نموذج تفاعل التعلم - يتتبع سلوكيات تعلم الطالب
    
    Stores individual learning interactions for FSLSM ML prediction
    يخزن تفاعلات التعلم الفردية للتنبؤ بـ FSLSM باستخدام ML
    """
    __tablename__ = "learning_interactions"
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(String, ForeignKey("users.user_id"), nullable=False, index=True)
    interaction_type = Column(String, nullable=False, index=True)  # video_view, reading_time, forum_post, quiz_attempt, etc.
    duration_seconds = Column(Integer, nullable=True)  # Duration of interaction in seconds
    content_type = Column(String, nullable=True)  # visual, verbal, theoretical, practical
    course_code = Column(String, nullable=True, index=True)  # Related course
    metadata = Column(JSON, nullable=True)  # Additional interaction metadata
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationship
    student = relationship("User", foreign_keys=[student_id], backref="learning_interactions")

class PeerMatch(Base):
    """
    Peer Match Model - AI-driven peer matching
    نموذج مطابقة الأقران - مطابقة الأقران المدفوعة بالذكاء الاصطناعي
    
    Stores matches between students for study groups and projects
    يخزن المطابقات بين الطلاب لمجموعات الدراسة والمشاريع
    """
    __tablename__ = "peer_matches"
    id = Column(Integer, primary_key=True, index=True)
    student_1_id = Column(String, ForeignKey("users.user_id"), nullable=False, index=True)
    student_2_id = Column(String, ForeignKey("users.user_id"), nullable=False, index=True)
    match_type = Column(String, nullable=False, index=True)  # study_group, project_team, tutoring
    compatibility_score = Column(Float, nullable=False)  # 0-1 compatibility score
    match_reason = Column(Text, nullable=True)  # Human-readable explanation
    course_code = Column(String, nullable=True, index=True)  # Related course (if applicable)
    status = Column(String, default="suggested", index=True)  # suggested, accepted, declined, completed
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    student_1 = relationship("User", foreign_keys=[student_1_id], backref="peer_matches_as_student_1")
    student_2 = relationship("User", foreign_keys=[student_2_id], backref="peer_matches_as_student_2")

class StudyGroup(Base):
    """
    Study Group Model - Organized study groups
    نموذج مجموعة الدراسة - مجموعات الدراسة المنظمة
    
    Stores study groups created from peer matches
    يخزن مجموعات الدراسة المنشأة من مطابقات الأقران
    """
    __tablename__ = "study_groups"
    id = Column(Integer, primary_key=True, index=True)
    course_code = Column(String, nullable=True, index=True)  # Related course
    group_type = Column(String, nullable=False)  # homogeneous, heterogeneous
    max_size = Column(Integer, default=5)  # Maximum group size
    current_size = Column(Integer, default=0)  # Current number of members
    members = Column(JSON, nullable=False)  # [{student_id, role, joined_at}, ...]
    description = Column(Text, nullable=True)  # Group description
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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
