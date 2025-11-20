"""
Security Module
===============
This module handles all security-related operations:
- Password hashing and verification (bcrypt)
- JWT token creation and validation
- User authentication and authorization
- OAuth2 password flow implementation

وحدة الأمان
============
هذه الوحدة تتعامل مع جميع عمليات الأمان:
- تشفير والتحقق من كلمات المرور (bcrypt)
- إنشاء والتحقق من رموز JWT
- مصادقة وتفويض المستخدمين
- تطبيق OAuth2 password flow
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Annotated
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
import bcrypt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_users_session, User
from config_manager import get_config

# ------------------------------------------------------------
# Security Settings
# إعدادات الأمان
# ------------------------------------------------------------
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError(
        "SECRET_KEY environment variable is not set. "
        "Please define it in your environment or .env file before starting the backend."
    )
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = get_config("security", {}).get("access_token_expire_minutes", 30)

# إعدادات تشفير كلمة المرور
# استخدام bcrypt مباشرة لتجنب مشاكل التوافق مع passlib
BCRYPT_ROUNDS = 12

# إعداد OAuth2
# ملاحظة: tokenUrl يجب أن يكون مسار كامل أو نسبي
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="token",
    scheme_name="OAuth2PasswordBearer"
)

# ------------------------------------------------------------
# وظائف تشفير كلمة المرور
# ------------------------------------------------------------

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify password against hashed password using bcrypt.
    / التحقق من تطابق كلمة المرور النصية مع المشفرة باستخدام bcrypt.
    
    Args:
        plain_password: Plain text password / كلمة المرور النصية
        hashed_password: Hashed password from database / كلمة المرور المشفرة من قاعدة البيانات
        
    Returns:
        True if password matches, False otherwise
        / True إذا تطابقت كلمة المرور، False خلاف ذلك
    """
    if isinstance(hashed_password, str):
        hashed_password = hashed_password.encode('utf-8')
    if isinstance(plain_password, str):
        plain_password = plain_password.encode('utf-8')
    return bcrypt.checkpw(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """
    Hash password using bcrypt.
    / تشفير كلمة المرور باستخدام bcrypt.
    
    Args:
        password: Plain text password to hash / كلمة المرور النصية للتشفير
        
    Returns:
        Hashed password string / سلسلة كلمة المرور المشفرة
        
    Note:
        Password length is limited to 72 bytes (bcrypt limit)
        / طول كلمة المرور محدود بـ 72 بايت (حد bcrypt)
    """
    if isinstance(password, str):
        password = password.encode('utf-8')
    # تقليل طول كلمة المرور إذا كانت أطول من 72 بايت (حد bcrypt)
    if len(password) > 72:
        password = password[:72]
    salt = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
    hashed = bcrypt.hashpw(password, salt)
    return hashed.decode('utf-8')

# ------------------------------------------------------------
# وظائف JWT
# ------------------------------------------------------------

def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """
    Create JWT access token.
    / إنشاء رمز وصول JWT.
    
    Args:
        data: Dictionary containing token payload (usually includes 'sub' for user_id)
        / قاموس يحتوي على بيانات الرمز (عادة يتضمن 'sub' لمعرف المستخدم)
        expires_delta: Optional custom expiration time / وقت انتهاء الصلاحية الاختياري
        
    Returns:
        Encoded JWT token string / سلسلة رمز JWT المشفر
        
    Example:
        >>> token = create_access_token({"sub": "user123"})
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> tuple[str, bool]:
    """
    Decode and validate JWT access token.
    / فك تشفير والتحقق من رمز الوصول JWT.
    
    Args:
        token: JWT token string / سلسلة رمز JWT
        
    Returns:
        Tuple of (user_id, is_demo) / مجموعة من (معرف_المستخدم، وضع_تجريبي)
        
    Raises:
        HTTPException: If token is invalid or expired
        / HTTPException: إذا كان الرمز غير صالح أو منتهي الصلاحية
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        is_demo: bool = payload.get("demo", False)
        if user_id is None:
            raise JWTError
        return user_id, is_demo
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

# ------------------------------------------------------------
# وظائف الاعتمادية (Dependencies)
# ------------------------------------------------------------

async def get_current_user(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_users_session)],
    token: Annotated[str, Depends(oauth2_scheme)]
) -> User:
    """
    Get current authenticated user from JWT token.
    / الحصول على المستخدم الحالي المصادق عليه من رمز JWT.
    
    This is a FastAPI dependency that:
    1. Extracts JWT token from Authorization header
    2. Decodes and validates the token
    3. Returns User object from database
    4. Handles demo mode users
    
    هذه دالة اعتمادية FastAPI تقوم بـ:
    1. استخراج رمز JWT من رأس Authorization
    2. فك التشفير والتحقق من الرمز
    3. إرجاع كائن User من قاعدة البيانات
    4. التعامل مع مستخدمي الوضع التجريبي
    
    Args:
        db: Database session / جلسة قاعدة البيانات
        token: JWT token from Authorization header / رمز JWT من رأس Authorization
        
    Returns:
        User object / كائن المستخدم
        
    Raises:
        HTTPException: If token is invalid or user not found
        / HTTPException: إذا كان الرمز غير صالح أو المستخدم غير موجود
    """
    token_data = getattr(request.state, "token_data", None)

    if token_data and token_data.get("user_id"):
        user_id = token_data["user_id"]
        is_demo = token_data.get("is_demo", False)
    else:
        user_id, is_demo = decode_access_token(token)
        request.state.token_data = {
            "user_id": user_id,
            "is_demo": is_demo,
            "raw_token": token,
        }
    
    # إذا كان الوضع التجريبي، نعيد كائن وهمي
    if is_demo:
        from types import SimpleNamespace
        demo_user = SimpleNamespace()
        demo_user.user_id = user_id
        demo_user.full_name = f"طالب تجريبي {user_id.replace('demo_', '')}"
        demo_user.email = None
        demo_user.role = "student"
        demo_user.is_demo = True
        return demo_user
    
    result = await db.execute(select(User).filter(User.user_id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user

def get_current_admin_user(
    current_user: Annotated[User, Depends(get_current_user)]
) -> User:
    """
    Get current user and verify admin role.
    / الحصول على المستخدم الحالي والتحقق من صلاحية الإداري.
    
    This is a FastAPI dependency that ensures the current user has admin role.
    
    هذه دالة اعتمادية FastAPI تضمن أن المستخدم الحالي لديه صلاحية الإداري.
    
    Args:
        current_user: Current authenticated user / المستخدم الحالي المصادق عليه
        
    Returns:
        User object with admin role / كائن المستخدم بصلاحية الإداري
        
    Raises:
        HTTPException: If user is not an admin (403 Forbidden)
        / HTTPException: إذا لم يكن المستخدم إداري (403 Forbidden)
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )
    return current_user
