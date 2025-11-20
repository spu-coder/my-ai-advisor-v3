import os
import sys
from fastapi import FastAPI, Depends, HTTPException, status, Request, Query
import logging
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Annotated, Dict, Any, Optional, List
from pydantic import BaseModel, Field, field_validator

# إضافة مسار backend إلى sys.path للسماح بالاستيراد المطلق
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# استيراد الخدمات والنماذج
from logging_config import setup_logging
from database import get_users_session, get_progress_session, get_notifications_session, init_db, ChatMessage
from security import get_current_user, get_current_admin_user
from security_middleware import (
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
    RequestSizeMiddleware,
    JWTAuthMiddleware,
    WAFMiddleware,
    InputSanitizationMiddleware,
    AuditLoggingMiddleware,
    sanitize_string,
    validate_user_id,
)
from services import users_service, progress_service, notifications_service, documents_service, graph_service, llm_service
from services.users_service import StudentCreate, AdminCreate, UserLogin, Token

# ------------------------------------------------------------
# إعداد التسجيل (Logging)
# ------------------------------------------------------------
setup_logging(logging.INFO)
logger = logging.getLogger("API_GATEWAY")

# ------------------------------------------------------------
# تهيئة التطبيق
# ------------------------------------------------------------
app = FastAPI(
    title="Smart Academic Advisor API Gateway",
    description="API Gateway and Request Router for the Microservices-based Academic Advisor System.",
    version="1.0.0",
    swagger_ui_init_oauth={
        "usePkceWithAuthorizationCodeGrant": False,
    },
)

# تهيئة قواعد البيانات (سيتم استدعاؤها في startup event)

# إعداد CORS
origins = [
    "http://localhost:8501",  # واجهة Streamlit
    "http://127.0.0.1:8501",
]

# Add security middlewares (order matters: last added = first executed)
# ترتيب المعالجة: CORS → Audit → SecurityHeaders → JWT → InputSanitization → WAF → RequestSize → RateLimit
# Processing order: CORS → Audit → SecurityHeaders → JWT → InputSanitization → WAF → RequestSize → RateLimit

# 1. RateLimit (last added = first executed in request flow)
# يحد من معدل الطلبات - يتم تنفيذه أولاً في تدفق الطلب
app.add_middleware(RateLimitMiddleware)

# 2. RequestSize (second in request flow)
# يحد من حجم الطلب - يتم تنفيذه ثانياً
app.add_middleware(RequestSizeMiddleware)

# 3. WAF (third in request flow)
# جدار حماية التطبيق - يتم تنفيذه ثالثاً
app.add_middleware(WAFMiddleware)

# 4. InputSanitization / Pydantic Validation (fourth in request flow)
# تنظيف والتحقق من المدخلات - يتم تنفيذه رابعاً
app.add_middleware(InputSanitizationMiddleware)

# 5. JWT Auth (fifth in request flow)
# مصادقة JWT - يتم تنفيذه خامساً
app.add_middleware(
    JWTAuthMiddleware,
    protected_paths=(
        "/chat",
        "/users",
        "/progress",
        "/notifications",
        "/documents",
        "/graph",
    ),
)

# 6. SecurityHeaders (sixth in request flow)
# رؤوس الأمان - يتم تنفيذه سادساً
app.add_middleware(SecurityHeadersMiddleware)

# 7. Audit Logging (seventh in request flow)
# تسجيل التدقيق - يتم تنفيذه سابعاً
app.add_middleware(AuditLoggingMiddleware)

# 8. CORS (last in request flow, first in response flow)
# CORS - يتم تنفيذه أخيراً في الطلب وأولاً في الاستجابة
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------------------------------------
# Startup Event - تهيئة قاعدة البيانات
# ------------------------------------------------------------
@app.on_event("startup")
async def startup_event():
    """تهيئة قاعدة البيانات عند بدء التطبيق"""
    await init_db()
    logger.info("Database initialized successfully")

# ------------------------------------------------------------
# نماذج Pydantic للطلبات
# ------------------------------------------------------------

class ChatRequest(BaseModel):
    """Chat request model with input validation / نموذج طلب الدردشة مع التحقق من المدخلات"""
    question: str = Field(..., min_length=1, max_length=2000, description="User question / سؤال المستخدم")
    user_id: str = Field(..., min_length=1, max_length=50, description="User ID for personalized context / معرف المستخدم للسياق الشخصي")
    
    @field_validator('question')
    @classmethod
    def validate_question(cls, v):
        """Sanitize and validate question input"""
        if not v or not v.strip():
            raise ValueError("Question cannot be empty")
        return sanitize_string(v, max_length=2000)
    
    @field_validator('user_id')
    @classmethod
    def validate_user_id(cls, v):
        """Validate user_id format"""
        if not validate_user_id(v):
            raise ValueError("Invalid user_id format")
        return v

class ProgressRecordCreate(BaseModel):
    """Progress record creation model with validation / نموذج إنشاء سجل التقدم مع التحقق"""
    user_id: str = Field(..., min_length=1, max_length=50, description="User ID / معرف المستخدم")
    course_code: str = Field(..., min_length=1, max_length=20, description="Course code / رمز المقرر")
    grade: str = Field(..., min_length=1, max_length=5, description="Grade / الدرجة")
    hours: int = Field(..., ge=1, le=10, description="Credit hours (1-10) / الساعات المعتمدة (1-10)")
    semester: str = Field(..., min_length=1, max_length=50, description="Semester / الفصل الدراسي")
    
    @field_validator('course_code')
    @classmethod
    def validate_course_code(cls, v: str) -> str:
        """Validate and sanitize course code / التحقق من رمز المقرر وتنظيفه"""
        v = sanitize_string(v.strip().upper(), max_length=20)
        if not v:
            raise ValueError("Course code cannot be empty")
        return v
    
    @field_validator('grade')
    @classmethod
    def validate_grade(cls, v: str) -> str:
        """Validate grade format / التحقق من صيغة الدرجة"""
        v = sanitize_string(v.strip().upper(), max_length=5)
        valid_grades = {'A+', 'A', 'A-', 'B+', 'B', 'B-', 'C+', 'C', 'C-', 'D+', 'D', 'F', 'P', 'NP'}
        if v not in valid_grades:
            raise ValueError(f"Invalid grade. Must be one of: {', '.join(sorted(valid_grades))}")
        return v
    
    @field_validator('user_id')
    @classmethod
    def validate_user_id(cls, v: str) -> str:
        """Validate user_id format / التحقق من صيغة معرف المستخدم"""
        if not validate_user_id(v):
            raise ValueError("Invalid user_id format")
        return v

class GPASimulationRequest(BaseModel):
    current_gpa: Optional[float] = Field(
        default=None,
        description="المعدل التراكمي الحالي (يتم حسابه تلقائياً إذا تُرك فارغاً)",
    )
    current_hours: Optional[int] = Field(
        default=None,
        description="اجمالي الساعات المكتملة (يتم حسابه تلقائياً إذا تُرك فارغاً)",
    )
    new_courses: Dict[str, int] = Field(..., description="{course_code: hours}")
    expected_grades: Dict[str, str] = Field(..., description="{course_code: grade}")

class SyncDataRequest(BaseModel):
    """Sync data request model with validation / نموذج طلب مزامنة البيانات مع التحقق"""
    password: str = Field(..., min_length=6, max_length=100, description="University system password / كلمة سر النظام الجامعي")
    
    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Sanitize password input / تنظيف إدخال كلمة المرور"""
        if not v or not v.strip():
            raise ValueError("Password cannot be empty")
        # لا نقوم بتنظيف كلمة المرور بشكل كامل لأنها قد تحتوي على أحرف خاصة
        return v.strip()


# ------------------------------------------------------------
# Helpers / وظائف مساعدة
# ------------------------------------------------------------

async def _get_chat_history(db_session: AsyncSession, user_id: str, limit: int = 10):
    """
    Fetch latest chat messages for the given user.
    / جلب أحدث رسائل الدردشة للمستخدم المحدد.
    
    Args:
        db_session: Database session / جلسة قاعدة البيانات
        user_id: User identifier / معرف المستخدم
        limit: Maximum number of messages to retrieve / الحد الأقصى لعدد الرسائل
        
    Returns:
        List of chat message records / قائمة سجلات رسائل الدردشة
    """
    result = await db_session.execute(
        select(ChatMessage)
        .filter(ChatMessage.user_id == user_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
    )
    records = result.scalars().all()
    return list(reversed(records))


def _serialize_chat_history(records) -> List[Dict[str, Any]]:
    """
    Serialize chat history records to dictionary format.
    / تحويل سجلات تاريخ الدردشة إلى صيغة قاموس.
    
    Args:
        records: List of chat message records / قائمة سجلات رسائل الدردشة
        
    Returns:
        List of dictionaries with chat history / قائمة قواميس مع تاريخ الدردشة
    """
    history = []
    for record in records:
        history.append(
            {
                "role": record.role,
                "content": record.content,
                "intent": record.intent,
                "timestamp": record.created_at.isoformat() if record.created_at else None,
            }
        )
    return history


async def _persist_chat_exchange(
    db_session: AsyncSession, 
    user_id: str, 
    question: str, 
    answer: str, 
    intent: Optional[str]
) -> None:
    """
    Store the user/assistant messages for conversation continuity.
    / تخزين رسائل المستخدم/المساعد لاستمرارية المحادثة.
    
    Args:
        db_session: Database session / جلسة قاعدة البيانات
        user_id: User identifier / معرف المستخدم
        question: User's question / سؤال المستخدم
        answer: Assistant's answer / إجابة المساعد
        intent: Detected intent (optional) / النية المكتشفة (اختياري)
    """
    try:
        user_msg = ChatMessage(
            user_id=user_id,
            role="user",
            content=question,
            intent=intent,
        )
        assistant_msg = ChatMessage(
            user_id=user_id,
            role="assistant",
            content=answer,
            intent=intent,
        )
        db_session.add_all([user_msg, assistant_msg])
        await db_session.commit()
    except Exception:
        await db_session.rollback()
        logger.exception("Failed to persist chat exchange for user %s", user_id)

# ------------------------------------------------------------
# مسارات الأمان (Authentication & Authorization)
# ------------------------------------------------------------

@app.post("/register/student", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def register_student(
    student_data: StudentCreate, 
    db: Annotated[AsyncSession, Depends(get_users_session)]
) -> Dict[str, Any]:
    """
    Register a new student account (requires university system verification).
    / تسجيل طالب جديد (يتطلب التحقق من النظام الجامعي).
    
    Args:
        student_data: Student registration data / بيانات تسجيل الطالب
        db: Database session / جلسة قاعدة البيانات
        
    Returns:
        Dictionary with created user data / قاموس يحتوي على بيانات المستخدم المنشأ
    """
    logger.info(f"Attempting to register student: {student_data.user_id}")
    try:
        new_user = await users_service.create_student(db, student_data)
        logger.info(f"Student registered successfully: {new_user['user_id']}")
        return new_user
    except HTTPException as e:
        logger.error(f"Registration failed for student {student_data.user_id}: {e.detail}")
        raise e
    except Exception as e:
        logger.error(f"Unexpected error during student registration: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="خطأ داخلي في تسجيل الطالب")

@app.post("/register/admin", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def register_admin(
    admin_data: AdminCreate,
    current_admin: Annotated[users_service.User, Depends(get_current_admin_user)],
    db: Annotated[AsyncSession, Depends(get_users_session)]
) -> Dict[str, Any]:
    """
    Create a new admin account (requires approval from existing admin).
    / إنشاء حساب أدمن جديد (يحتاج موافقة من أدمن رئيسي).
    
    Args:
        admin_data: Admin registration data / بيانات تسجيل الأدمن
        current_admin: Current authenticated admin user / المستخدم الأدمن المصادق عليه حالياً
        db: Database session / جلسة قاعدة البيانات
        
    Returns:
        Dictionary with created admin data / قاموس يحتوي على بيانات الأدمن المنشأ
    """
    logger.warning(f"Admin {current_admin.user_id} attempting to create new admin: {admin_data.user_id}")
    try:
        new_user = await users_service.create_admin(db, admin_data, current_admin)
        logger.warning(f"Admin created successfully: {new_user['user_id']} by {current_admin.user_id}")
        return new_user
    except HTTPException as e:
        logger.error(f"Admin creation failed: {e.detail}")
        raise e
    except Exception as e:
        logger.error(f"Unexpected error during admin creation: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="خطأ داخلي في إنشاء حساب الأدمن")

@app.post("/register/admin/initial", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def register_initial_admin(
    admin_data: AdminCreate,
    db: Annotated[AsyncSession, Depends(get_users_session)]
) -> Dict[str, Any]:
    """
    Create initial admin account (only if no admin exists).
    / إنشاء حساب أدمن أولي (فقط إذا لم يكن هناك أدمن موجود).
    
    Args:
        admin_data: Admin registration data / بيانات تسجيل الأدمن
        db: Database session / جلسة قاعدة البيانات
        
    Returns:
        Dictionary with created admin data / قاموس يحتوي على بيانات الأدمن المنشأ
        
    Raises:
        HTTPException: If admin already exists or creation fails
        / HTTPException: إذا كان الأدمن موجوداً بالفعل أو فشل الإنشاء
    """
    # التحقق من وجود أدمن موجود
    result = await db.execute(select(users_service.User).filter(users_service.User.role == "admin"))
    existing_admin = result.scalar_one_or_none()
    if existing_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="يوجد أدمن موجود بالفعل. يجب تسجيل الدخول كأدمن لإنشاء حسابات جديدة."
        )
    
    logger.warning(f"Creating initial admin account: {admin_data.user_id}")
    try:
        # إنشاء حساب الأدمن مباشرة بدون الحاجة لموافقة
        from security import get_password_hash
        
        # التحقق من أن المعرف غير مستخدم
        result = await db.execute(select(users_service.User).filter(users_service.User.user_id == admin_data.user_id))
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="معرف المستخدم مسجل بالفعل")
        
        # التحقق من أن البريد الإلكتروني غير مستخدم
        result = await db.execute(select(users_service.User).filter(users_service.User.email == admin_data.email))
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="البريد الإلكتروني مسجل بالفعل")
        
        # تشفير كلمة المرور
        hashed_password = get_password_hash(admin_data.password)
        
        db_user = users_service.User(
            user_id=admin_data.user_id,
            full_name=admin_data.full_name,
            email=admin_data.email,
            hashed_password=hashed_password,
            university_password=None,
            role="admin"
        )
        db.add(db_user)
        await db.commit()
        await db.refresh(db_user)
        
        logger.warning(f"Initial admin created successfully: {db_user.user_id}")
        return {
            "user_id": db_user.user_id, 
            "full_name": db_user.full_name, 
            "email": db_user.email, 
            "role": db_user.role
        }
    except HTTPException as e:
        logger.error(f"Initial admin creation failed: {e.detail}")
        raise e
    except Exception as e:
        logger.error(f"Unexpected error during initial admin creation: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="خطأ داخلي في إنشاء حساب الأدمن الأولي")

@app.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_users_session)]
) -> Token:
    """
    Login and get access token (JWT) - OAuth2 password flow.
    / تسجيل الدخول والحصول على رمز الوصول (JWT) - OAuth2 password flow.
    
    Args:
        form_data: OAuth2 password form data / بيانات نموذج OAuth2 password
        db: Database session / جلسة قاعدة البيانات
        
    Returns:
        Token object with access token and user info / كائن Token مع رمز الوصول ومعلومات المستخدم
    """
    logger.info(f"Attempting login with identifier: {form_data.username}")
    try:
        token_data = users_service.login_for_access_token(db, form_data.username, form_data.password, allow_demo=False)
        logger.info(f"Login successful: {form_data.username}, Demo: {token_data.is_demo}")
        return token_data
    except HTTPException as e:
        logger.warning(f"Login failed for {form_data.username}: {e.detail}")
        raise e

@app.post("/token/json", response_model=Token)
async def login_for_access_token_json(
    user_data: UserLogin,
    db: Annotated[AsyncSession, Depends(get_users_session)],
    allow_demo: bool = Query(False, description="السماح بالوضع التجريبي")
) -> Token:
    """
    Login and get access token (JWT) - JSON format only.
    / تسجيل الدخول والحصول على رمز الوصول (JWT) - JSON format فقط.
    
    Args:
        user_data: User login credentials / بيانات اعتماد تسجيل الدخول
        db: Database session / جلسة قاعدة البيانات
        allow_demo: Allow demo mode / السماح بالوضع التجريبي
        
    Returns:
        Token object with access token and user info / كائن Token مع رمز الوصول ومعلومات المستخدم
    """
    logger.info(f"Attempting login with identifier: {user_data.identifier}, allow_demo: {allow_demo}")
    try:
        # تنظيف المدخلات
        identifier = user_data.identifier.strip() if user_data.identifier else ""
        password = user_data.password if user_data.password else ""
        
        if not identifier or not password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="يجب إدخال المعرف وكلمة المرور"
            )
        
        token_data = await users_service.login_for_access_token(db, identifier, password, allow_demo)
        logger.info(f"Login successful: {identifier}, Demo: {token_data.is_demo}")
        return token_data
    except HTTPException as e:
        logger.warning(f"Login failed for {user_data.identifier}: {e.detail}")
        raise e
    except Exception as e:
        logger.error(f"Unexpected error during login: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="حدث خطأ غير متوقع أثناء تسجيل الدخول"
        )

@app.get("/users/me", response_model=Dict[str, Any])
async def read_users_me(
    current_user: Annotated[users_service.User, Depends(get_current_user)]
) -> Dict[str, Any]:
    """
    Get current user information (protected route).
    / الحصول على معلومات المستخدم الحالي (مسار محمي).
    
    Args:
        current_user: Authenticated user from JWT token / المستخدم المصادق عليه من رمز JWT
        
    Returns:
        Dictionary with user information / قاموس يحتوي على معلومات المستخدم
    """
    result = {
        "user_id": current_user.user_id, 
        "full_name": current_user.full_name, 
        "email": getattr(current_user, 'email', None), 
        "role": current_user.role
    }
    if hasattr(current_user, 'is_demo'):
        result["is_demo"] = current_user.is_demo
    return result

@app.post("/users/sync-data", response_model=Dict[str, Any])
async def sync_student_data(
    sync_request: SyncDataRequest,
    current_user: Annotated[users_service.User, Depends(get_current_user)],
    db_users: Annotated[AsyncSession, Depends(get_users_session)],
    db_progress: Annotated[AsyncSession, Depends(get_progress_session)]
) -> Dict[str, Any]:
    """
    Sync student data from university system and save it (protected route).
    / جمع بيانات الطالب من النظام الجامعي وحفظها (محمي).
    
    Args:
        sync_request: Sync request with university password / طلب المزامنة مع كلمة سر النظام الجامعي
        current_user: Authenticated user / المستخدم المصادق عليه
        db_users: Users database session / جلسة قاعدة بيانات المستخدمين
        db_progress: Progress database session / جلسة قاعدة بيانات التقدم
        
    Returns:
        Dictionary with sync results / قاموس يحتوي على نتائج المزامنة
    """
    # التحقق من الوضع التجريبي
    if hasattr(current_user, 'is_demo') and current_user.is_demo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="الوضع التجريبي لا يدعم جمع البيانات الشخصية"
        )
    
    # التحقق من أن المستخدم طالب
    if current_user.role != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="هذه الميزة متاحة للطلاب فقط"
        )
    
    logger.info(f"Syncing data for student: {current_user.user_id}")
    
    try:
        result = await users_service.sync_student_data_from_university(
            db_users, db_progress, current_user.user_id, sync_request.password
        )
        
        if result.get('success'):
            logger.info(f"Data sync successful for student: {current_user.user_id}")
            return result
        else:
            logger.error(f"Data sync failed for student {current_user.user_id}: {result.get('error')}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get('error', 'فشل جمع البيانات')
            )
    except Exception as e:
        logger.error(f"Error syncing data for student {current_user.user_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"خطأ في جمع البيانات: {str(e)}"
        )

# ------------------------------------------------------------
# مسارات الخدمات (مع تطبيق الأمان)
# ------------------------------------------------------------

# مسار الدردشة (محمي)
@app.post("/chat", response_model=Dict[str, Any])
async def chat_with_advisor(
    chat_request: ChatRequest,
    current_user: Annotated[users_service.User, Depends(get_current_user)],
    db_users: Annotated[AsyncSession, Depends(get_users_session)],
    db_progress: Annotated[AsyncSession, Depends(get_progress_session)],
    db_notifications: Annotated[AsyncSession, Depends(get_notifications_session)],
):
    """
    Main chat endpoint (Agentic RAG).
    / مسار الدردشة الرئيسي (Agentic RAG).
    
    Args:
        chat_request: Chat request with question and user_id
        current_user: Authenticated user from JWT token
        db_users: Users database session
        db_progress: Progress database session
        db_notifications: Notifications database session
        
    Returns:
        Dict containing answer, source, and intent
        
    Raises:
        HTTPException: If authorization fails or processing error occurs
    """
    logger.info(f"Chat request from user {current_user.user_id}: {chat_request.question[:100]}...")
    
    # Authorization check: verify user_id matches authenticated user
    # التحقق من التفويض: التحقق من تطابق معرف المستخدم مع المستخدم المصادق عليه
    if chat_request.user_id != current_user.user_id:
        logger.warning(f"Authorization failed: user {current_user.user_id} tried to query for {chat_request.user_id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Cannot query for another user's data / لا يمكن الاستعلام عن بيانات مستخدم آخر"
        )
    
    # Check if demo mode
    # التحقق من الوضع التجريبي
    is_demo = hasattr(current_user, 'is_demo') and current_user.is_demo
    if is_demo:
        logger.info(f"Demo user {current_user.user_id} using chat - limited functionality")
    
    # جلسة الإشعارات متوفرة للاستخدام المستقبلي
    _ = db_notifications

    try:
        chat_history_records = []
        if not is_demo:
            chat_history_records = await _get_chat_history(db_users, current_user.user_id, limit=10)
        chat_history = _serialize_chat_history(chat_history_records)

        # إعداد ServiceAdapter لفصل LLM Service عن قاعدة البيانات
        # Setup ServiceAdapter to decouple LLM Service from database
        from services.service_interface import ServiceAdapter
        service_adapter = ServiceAdapter(
            documents_service=documents_service,
            progress_service=progress_service,
            graph_service=graph_service,
            progress_db=db_progress,
            users_db=db_users,
        )
        
        # استخدام user_id فعال (None للوضع التجريبي)
        effective_user_id = chat_request.user_id if not is_demo else None
        
        # استدعاء الدالة غير المتزامنة مباشرة
        response_obj = await llm_service.process_agentic_query(
            question=chat_request.question,
            user_id=effective_user_id,
            service_adapter=service_adapter,
            is_demo=is_demo,
            chat_history=chat_history
        )
        
        # تحويل الاستجابة إلى قاموس
        response = {
            "answer": response_obj.answer,
            "source": response_obj.source,
            "intent": response_obj.intent
        }
        
        logger.info(f"Chat response generated for user {current_user.user_id}. Intent: {response.get('intent')}")

        if not is_demo and response_obj.intent != "clarify":
            await _persist_chat_exchange(
                db_users,
                current_user.user_id,
                chat_request.question,
                response_obj.answer,
                response_obj.intent,
            )
        
        # Add demo warning
        # إضافة تحذير للوضع التجريبي
        if is_demo:
            response['demo_warning'] = "⚠️ أنت في الوضع التجريبي. الإجابات لا تعتمد على بياناتك الشخصية."
        
        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing chat request for user {current_user.user_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="Error processing chat request / خطأ في معالجة طلب الدردشة"
        )

# مسارات تقدم الطلاب (محمية)
@app.post("/progress/record", response_model=Dict[str, Any])
async def record_progress(
    record: ProgressRecordCreate,
    current_user: Annotated[users_service.User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_progress_session)],
) -> Dict[str, Any]:
    """
    Record a completed course (protected route).
    / تسجيل مقرر مكتمل (محمي).
    
    Args:
        record: Progress record data / بيانات سجل التقدم
        current_user: Authenticated user / المستخدم المصادق عليه
        db: Progress database session / جلسة قاعدة بيانات التقدم
        
    Returns:
        Dictionary with recorded progress data / قاموس يحتوي على بيانات التقدم المسجلة
    """
    if record.user_id != current_user.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot record progress for another user")
    
    logger.info(f"Recording progress for user {current_user.user_id}: {record.course_code}")
    return await progress_service.record_progress(db, record.model_dump())

@app.get("/progress/analyze/{user_id}", response_model=Dict[str, Any])
async def analyze_progress(
    user_id: str,
    current_user: Annotated[users_service.User, Depends(get_current_user)],
    db_progress: Annotated[AsyncSession, Depends(get_progress_session)],
    db_users: Annotated[AsyncSession, Depends(get_users_session)],
) -> Dict[str, Any]:
    """
    Analyze academic progress (protected route).
    / تحليل التقدم الأكاديمي (محمي).
    
    Args:
        user_id: User identifier / معرف المستخدم
        current_user: Authenticated user / المستخدم المصادق عليه
        db_progress: Progress database session / جلسة قاعدة بيانات التقدم
        db_users: Users database session / جلسة قاعدة بيانات المستخدمين
        
    Returns:
        Dictionary with progress analysis / قاموس يحتوي على تحليل التقدم
    """
    # التحقق من الوضع التجريبي
    if hasattr(current_user, 'is_demo') and current_user.is_demo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="الوضع التجريبي لا يدعم تحليل التقدم الشخصي"
        )
    
    if user_id != current_user.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot analyze progress for another user")
    
    # التحقق من أن المستخدم طالب
    if current_user.role != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="هذه الميزة متاحة للطلاب فقط"
        )
    
    logger.info(f"Analyzing progress for user {user_id}")
    return await progress_service.analyze_progress(db_progress, db_users, user_id)

@app.post("/progress/simulate-gpa", response_model=Dict[str, Any])
async def simulate_gpa(
    simulation_request: GPASimulationRequest,
    current_user: Annotated[users_service.User, Depends(get_current_user)],
    db_progress: Annotated[AsyncSession, Depends(get_progress_session)],
) -> Dict[str, Any]:
    """
    Simulate GPA calculation (protected route).
    / محاكاة المعدل التراكمي (محمي).
    
    Args:
        simulation_request: GPA simulation request / طلب محاكاة المعدل التراكمي
        current_user: Authenticated user / المستخدم المصادق عليه
        db_progress: Progress database session / جلسة قاعدة بيانات التقدم
        
    Returns:
        Dictionary with simulation results / قاموس يحتوي على نتائج المحاكاة
    """
    logger.info(f"Simulating GPA for user {current_user.user_id}")
    return await progress_service.simulate_gpa(
        db_progress,
        current_user.user_id,
        simulation_request.model_dump(),
    )

# مسارات الإشعارات (محمية)
@app.get("/notifications/{user_id}", response_model=list[Dict[str, Any]])
async def get_user_notifications(
    user_id: str,
    current_user: Annotated[users_service.User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_notifications_session)],
) -> List[Dict[str, Any]]:
    """
    Get user notifications (protected route).
    / الحصول على إشعارات المستخدم (محمي).
    
    Args:
        user_id: User identifier / معرف المستخدم
        current_user: Authenticated user / المستخدم المصادق عليه
        db: Notifications database session / جلسة قاعدة بيانات الإشعارات
        
    Returns:
        List of notification dictionaries / قائمة قواميس الإشعارات
    """
    if user_id != current_user.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot view another user's notifications")
    
    logger.info(f"Fetching notifications for user {user_id}")
    return await notifications_service.get_notifications(db, user_id)

# مسارات المستندات (محمية - للإداريين فقط)
@app.post("/documents/ingest", response_model=Dict[str, Any])
async def ingest_documents_route(
    current_admin: Annotated[users_service.User, Depends(get_current_admin_user)]
) -> Dict[str, Any]:
    """
    Ingest documents into the system (admin only, protected route).
    / فهرسة المستندات (محمي للإداريين).
    
    Args:
        current_admin: Authenticated admin user / المستخدم الأدمن المصادق عليه
        
    Returns:
        Dictionary with ingestion results / قاموس يحتوي على نتائج الفهرسة
    """
    logger.warning(f"Admin user {current_admin.user_id} is initiating document ingestion.")
    try:
        return documents_service.ingest_documents()
    except Exception as e:
        logger.error(f"Error during document ingestion: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error during document ingestion")

# مسارات الرسم البياني (محمية - للإداريين فقط)
@app.post("/graph/ingest", response_model=Dict[str, Any])
async def ingest_graph_data_route(
    current_admin: Annotated[users_service.User, Depends(get_current_admin_user)]
) -> Dict[str, Any]:
    """
    Ingest graph data into Neo4j (admin only, protected route).
    / فهرسة بيانات الرسم البياني (محمي للإداريين).
    
    Args:
        current_admin: Authenticated admin user / المستخدم الأدمن المصادق عليه
        
    Returns:
        Dictionary with ingestion results / قاموس يحتوي على نتائج الفهرسة
    """
    logger.warning(f"Admin user {current_admin.user_id} is initiating graph data ingestion.")
    try:
        return graph_service.ingest_graph_data()
    except Exception as e:
        logger.error(f"Error during graph data ingestion: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error during graph data ingestion")

@app.get("/graph/skills/{course_code}", response_model=Dict[str, Any])
async def get_skills_for_course_route(
    course_code: str, 
    current_user: Annotated[users_service.User, Depends(get_current_user)]
) -> Dict[str, Any]:
    """
    Get skills for a specific course (protected route).
    / الحصول على المهارات لمقرر معين (محمي).
    
    Args:
        course_code: Course code / رمز المقرر
        current_user: Authenticated user / المستخدم المصادق عليه
        
    Returns:
        Dictionary with course code and skills list / قاموس يحتوي على رمز المقرر وقائمة المهارات
    """
    logger.info(f"User {current_user.user_id} querying skills for course {course_code}")
    try:
        skills = graph_service.get_skills_for_course(course_code)
        return {"course_code": course_code, "skills": skills}
    except Exception as e:
        logger.error(f"Error querying graph for course {course_code}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error querying graph data")

# ------------------------------------------------------------
# مسار فحص الصحة (Health Check)
# ------------------------------------------------------------

@app.get("/health")
async def health_check() -> Dict[str, str]:
    """
    Health check endpoint.
    / مسار فحص الصحة.
    
    Returns:
        Dictionary with service status / قاموس يحتوي على حالة الخدمة
    """
    return {"status": "ok", "service": "API Gateway"}
