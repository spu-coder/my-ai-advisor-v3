#!/usr/bin/env python3
"""
سكريبت لإنشاء حسابات أدمن افتراضية
Script to create default admin accounts
"""
import sys
import os

# إضافة مسار backend إلى sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_users_session, User
from security import get_password_hash
import logging
import getpass

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# حسابات الأدمن الافتراضية
DEFAULT_ADMINS = [
    {
        "user_id": "admin",
        "full_name": "المسؤول الرئيسي",
        "email": "admin@example.com",
    },
    {
        "user_id": "admin1",
        "full_name": "مسؤول النظام",
        "email": "admin1@example.com",
    },
    {
        "user_id": "superadmin",
        "full_name": "المسؤول الأعلى",
        "email": "superadmin@example.com",
    }
]

def _resolve_password(admin_id: str) -> str:
    """
    الحصول على كلمة مرور الحساب من متغيرات البيئة أو من إدخال المستخدم.
    يفضل استخدام متغيرات البيئة مثل ADMIN_PASSWORD_ADMIN.
    """
    env_key = f"ADMIN_PASSWORD_{admin_id.upper()}"
    password = os.getenv(env_key) or os.getenv("DEFAULT_ADMIN_PASSWORD")

    if password:
        return password

    if sys.stdin.isatty():
        return getpass.getpass(
            prompt=f"أدخل كلمة المرور للحساب {admin_id}: "
        )

    raise RuntimeError(
        f"لم يتم توفير كلمة مرور لـ {admin_id}. "
        f"يرجى تعيين المتغير {env_key} أو DEFAULT_ADMIN_PASSWORD قبل التشغيل."
    )

def create_default_admins():
    """إنشاء حسابات أدمن افتراضية"""
    logger.info("بدء إنشاء حسابات الأدمن الافتراضية...")
    
    # الحصول على جلسة قاعدة البيانات
    db_gen = get_users_session()
    db = next(db_gen)
    
    created_count = 0
    skipped_count = 0
    
    try:
        for admin_data in DEFAULT_ADMINS:
            # التحقق من وجود الحساب
            existing_user = db.query(User).filter(
                (User.user_id == admin_data["user_id"]) | 
                (User.email == admin_data["email"])
            ).first()
            
            if existing_user:
                logger.warning(f"⚠️ الحساب موجود بالفعل: {admin_data['user_id']} ({admin_data['email']})")
                skipped_count += 1
                continue
            
            # الحصول على كلمة المرور من البيئة أو من المستخدم
            password = _resolve_password(admin_data["user_id"])
            if not password:
                logger.error(f"⚠️ لا يمكن إنشاء الحساب {admin_data['user_id']} بدون كلمة مرور صالحة.")
                skipped_count += 1
                continue

            hashed_password = get_password_hash(password)
            
            new_admin = User(
                user_id=admin_data["user_id"],
                full_name=admin_data["full_name"],
                email=admin_data["email"],
                hashed_password=hashed_password,
                role="admin",
                university_password=None
            )
            
            db.add(new_admin)
            db.commit()
            db.refresh(new_admin)
            
            logger.info(f"✅ تم إنشاء حساب أدمن: {admin_data['user_id']} ({admin_data['email']})")
            created_count += 1
        
        logger.info(f"\n{'='*60}")
        logger.info(f"✅ تم إنشاء {created_count} حساب أدمن")
        logger.info(f"⚠️ تم تخطي {skipped_count} حساب (موجود بالفعل)")
        logger.info(f"{'='*60}\n")
        
        # طباعة معلومات الحسابات
        logger.info("📋 تم إنشاء الحسابات المطلوبة بدون تخزين كلمات المرور في السجلات.")
        
    except Exception as e:
        logger.error(f"❌ خطأ في إنشاء حسابات الأدمن: {str(e)}", exc_info=True)
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    try:
        create_default_admins()
        logger.info("✅ اكتمل إنشاء حسابات الأدمن بنجاح!")
    except Exception as e:
        logger.error(f"❌ فشل إنشاء حسابات الأدمن: {str(e)}")
        sys.exit(1)

