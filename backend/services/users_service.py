import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from fastapi import HTTPException, status
from typing import Dict, Any
from database import User, ProgressRecord, StudentAcademicInfo, RemainingCourse
from security import get_password_hash, verify_password, create_access_token
from datetime import timedelta, datetime
from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional, Union
import logging
import json

logger = logging.getLogger("USERS_SERVICE")

# استيراد خدمة النظام الجامعي
from services.university_system_service import UniversitySystemService

# ------------------------------------------------------------
# نماذج Pydantic للأمان
# ------------------------------------------------------------

class StudentCreate(BaseModel):
    """نموذج إنشاء حساب طالب"""
    user_id: str = Field(..., description="الرقم الجامعي")
    full_name: str = Field(..., description="الاسم الكامل")
    email: Optional[str] = Field(None, description="البريد الإلكتروني (اختياري)")
    password: str = Field(..., description="كلمة سر النظام الجامعي")
    
    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        """التحقق من صحة البريد الإلكتروني إذا كان موجوداً"""
        if v and v.strip():
            # التحقق من أن البريد يحتوي على @
            if '@' not in v:
                raise ValueError('البريد الإلكتروني يجب أن يحتوي على @')
        return v if v and v.strip() else None

class AdminCreate(BaseModel):
    """نموذج إنشاء حساب أدمن (يحتاج موافقة)"""
    user_id: str = Field(..., description="معرف الأدمن (فريد)")
    full_name: str = Field(..., description="الاسم الكامل")
    email: EmailStr = Field(..., description="البريد الإلكتروني (مطلوب للأدمن)")
    password: str = Field(..., min_length=6, description="كلمة المرور (مطلوبة للأدمن)")

class UserLogin(BaseModel):
    """نموذج تسجيل الدخول - يدعم الطالب والأدمن"""
    identifier: str = Field(..., description="الرقم الجامعي (للطالب) أو البريد الإلكتروني (للأدمن)")
    password: str = Field(..., description="كلمة المرور")

class Token(BaseModel):
    access_token: str
    token_type: str
    user_id: str
    role: str
    is_demo: bool = False  # هل هو وضع تجريبي

# ------------------------------------------------------------
# وظائف الخدمة
# ------------------------------------------------------------

async def create_student(db: AsyncSession, student_data: StudentCreate) -> Dict[str, Any]:
    """إنشاء حساب طالب جديد مع التحقق من النظام الجامعي."""
    # التحقق من أن الرقم الجامعي غير مستخدم
    result = await db.execute(select(User).filter(User.user_id == student_data.user_id))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="الرقم الجامعي مسجل بالفعل")
    
    # التحقق من البريد الإلكتروني إذا كان موجوداً
    if student_data.email:
        result = await db.execute(select(User).filter(User.email == student_data.email))
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="البريد الإلكتروني مسجل بالفعل")
    
    # التحقق من صحة بيانات تسجيل الدخول في النظام الجامعي
    logger.info(f"التحقق من بيانات الطالب {student_data.user_id} في النظام الجامعي...")
    try:
        university_service = UniversitySystemService()
        login_success = university_service.login(student_data.user_id, student_data.password)
        university_service.close()
        
        if not login_success:
            # السماح بإنشاء الحساب حتى لو فشل التحقق (للتطوير)
            # في الإنتاج، يجب إزالة هذا التعليق
            logger.warning(f"⚠️ فشل التحقق من بيانات الطالب {student_data.user_id} في النظام الجامعي، لكن سيتم إنشاء الحساب")
            # raise HTTPException(
            #     status_code=400, 
            #     detail="فشل التحقق من بيانات تسجيل الدخول في النظام الجامعي. تأكد من صحة الرقم الجامعي وكلمة المرور."
            # )
    except Exception as e:
        logger.error(f"❌ خطأ في الاتصال بالنظام الجامعي: {str(e)}")
        # السماح بإنشاء الحساب حتى لو فشل الاتصال (للتطوير)
        logger.warning(f"⚠️ فشل الاتصال بالنظام الجامعي، لكن سيتم إنشاء الحساب: {str(e)}")
    
    # تشفير كلمة المرور قبل الحفظ
    hashed_password = get_password_hash(student_data.password)
    university_password = get_password_hash(student_data.password)
    
    db_user = User(
        user_id=student_data.user_id,
        full_name=student_data.full_name,
        email=student_data.email,
        hashed_password=hashed_password,
        university_password=university_password,
        role="student"
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    logger.info(f"تم إنشاء حساب طالب بنجاح: {db_user.user_id}")
    return {
        "user_id": db_user.user_id, 
        "full_name": db_user.full_name, 
        "email": db_user.email, 
        "role": db_user.role
    }

async def create_admin(db: AsyncSession, admin_data: AdminCreate, approved_by: User) -> Dict[str, Any]:
    """إنشاء حساب أدمن جديد (يحتاج موافقة من أدمن رئيسي)."""
    # التحقق من أن الموافق هو أدمن
    if approved_by.role != "admin":
        raise HTTPException(status_code=403, detail="فقط الأدمن يمكنهم إنشاء حسابات أدمن جديدة")
    
    # التحقق من أن المعرف غير مستخدم
    result = await db.execute(select(User).filter(User.user_id == admin_data.user_id))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="معرف المستخدم مسجل بالفعل")
    
    # التحقق من أن البريد الإلكتروني غير مستخدم
    result = await db.execute(select(User).filter(User.email == admin_data.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="البريد الإلكتروني مسجل بالفعل")
    
    # تشفير كلمة المرور
    hashed_password = get_password_hash(admin_data.password)
    
    db_user = User(
        user_id=admin_data.user_id,
        full_name=admin_data.full_name,
        email=admin_data.email,
        hashed_password=hashed_password,
        university_password=None,  # الأدمن لا يحتاج كلمة سر النظام الجامعي
        role="admin"
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    
    logger.warning(f"تم إنشاء حساب أدمن جديد: {db_user.user_id} بواسطة: {approved_by.user_id}")
    return {
        "user_id": db_user.user_id, 
        "full_name": db_user.full_name, 
        "email": db_user.email, 
        "role": db_user.role
    }

async def authenticate_user(db: AsyncSession, identifier: str, password: str, allow_demo: bool = False) -> Union[User, Dict[str, Any]]:
    """
    مصادقة المستخدم - يدعم الطالب والأدمن.
    
    Args:
        identifier: الرقم الجامعي (للطالب) أو البريد الإلكتروني (للأدمن)
        password: كلمة المرور
        allow_demo: السماح بوضع تجريبي إذا فشل تسجيل الدخول
        
    Returns:
        User object أو dict للوضع التجريبي
    """
    # محاولة البحث كأدمن (بالبريد الإلكتروني)
    result = await db.execute(select(User).filter(User.email == identifier))
    user = result.scalar_one_or_none()
    
    if user and user.role == "admin":
        # مصادقة الأدمن
        if verify_password(password, user.hashed_password):
            logger.info(f"تم تسجيل دخول أدمن: {user.user_id}")
            return user
        else:
            raise HTTPException(
                status_code=401,
                detail="البريد الإلكتروني أو كلمة المرور غير صحيحة"
            )
    
    # محاولة البحث كطالب (بالرقم الجامعي)
    result = await db.execute(select(User).filter(User.user_id == identifier))
    user = result.scalar_one_or_none()
    
    if user and user.role == "student":
        # التحقق من كلمة المرور المحلية أولاً
        if verify_password(password, user.hashed_password) or verify_password(password, user.university_password or ""):
            logger.info(f"تم تسجيل دخول طالب: {user.user_id}")
            return user
        
        # محاولة التحقق من النظام الجامعي
        try:
            university_service = UniversitySystemService()
            if university_service.login(identifier, password):
                university_service.close()
                # تحديث كلمة المرور المشفرة
                user.university_password = get_password_hash(password)
                if not user.hashed_password:
                    user.hashed_password = get_password_hash(password)
                await db.commit()
                logger.info(f"تم تسجيل دخول طالب: {user.user_id}")
                return user
            else:
                university_service.close()
        except Exception as e:
            logger.warning(f"⚠️ فشل الاتصال بالنظام الجامعي: {str(e)}")
        
        # إذا فشل تسجيل الدخول وسمح بالوضع التجريبي
        if allow_demo:
            logger.info(f"فشل تسجيل الدخول للطالب {identifier} - استخدام الوضع التجريبي")
            return {
                "user_id": f"demo_{identifier}",
                "full_name": f"طالب تجريبي {identifier}",
                "email": None,
                "role": "student",
                "is_demo": True
            }
        
        # السماح بتسجيل الدخول حتى لو فشل التحقق (للتطوير)
        logger.warning(f"⚠️ فشل التحقق من النظام الجامعي، لكن سيتم السماح بتسجيل الدخول")
        return user
    
    # إذا لم يكن المستخدم مسجلاً وكان طالباً، نحاول إنشاء حساب تلقائياً
    if not user:
        # محاولة تسجيل الدخول إلى النظام الجامعي
        try:
            university_service = UniversitySystemService()
            login_success = university_service.login(identifier, password)
            university_service.close()
            
            if login_success:
                # إنشاء حساب جديد تلقائياً
                hashed_password = get_password_hash(password)
                university_password = get_password_hash(password)
                
                db_user = User(
                    user_id=identifier,
                    full_name=f"طالب {identifier}",
                    email=None,
                    hashed_password=hashed_password,
                    university_password=university_password,
                    role="student"
                )
                db.add(db_user)
                await db.commit()
                await db.refresh(db_user)
                logger.info(f"تم إنشاء حساب طالب تلقائياً: {db_user.user_id}")
                return db_user
            else:
                # إذا فشل تسجيل الدخول وسمح بالوضع التجريبي
                if allow_demo:
                    logger.info(f"فشل تسجيل الدخول للطالب {identifier} - استخدام الوضع التجريبي")
                    return {
                        "user_id": f"demo_{identifier}",
                        "full_name": f"طالب تجريبي {identifier}",
                        "email": None,
                        "role": "student",
                        "is_demo": True
                    }
                # السماح بإنشاء الحساب حتى لو فشل التحقق (للتطوير)
                logger.warning(f"⚠️ فشل التحقق من بيانات الطالب {identifier}، لكن سيتم إنشاء الحساب")
                hashed_password = get_password_hash(password)
                university_password = get_password_hash(password)
                
                db_user = User(
                    user_id=identifier,
                    full_name=f"طالب {identifier}",
                    email=None,
                    hashed_password=hashed_password,
                    university_password=university_password,
                    role="student"
                )
                db.add(db_user)
                await db.commit()
                await db.refresh(db_user)
                logger.info(f"تم إنشاء حساب طالب تلقائياً (بدون تحقق): {db_user.user_id}")
                return db_user
        except Exception as e:
            logger.error(f"❌ خطأ في الاتصال بالنظام الجامعي: {str(e)}")
            # إذا فشل الاتصال وسمح بالوضع التجريبي
            if allow_demo:
                logger.info(f"فشل الاتصال للطالب {identifier} - استخدام الوضع التجريبي")
                return {
                    "user_id": f"demo_{identifier}",
                    "full_name": f"طالب تجريبي {identifier}",
                    "email": None,
                    "role": "student",
                    "is_demo": True
                }
            # السماح بإنشاء الحساب حتى لو فشل الاتصال (للتطوير)
            logger.warning(f"⚠️ فشل الاتصال بالنظام الجامعي، لكن سيتم إنشاء الحساب: {str(e)}")
            hashed_password = get_password_hash(password)
            university_password = get_password_hash(password)
            
            db_user = User(
                user_id=identifier,
                full_name=f"طالب {identifier}",
                email=None,
                hashed_password=hashed_password,
                university_password=university_password,
                role="student"
            )
            db.add(db_user)
            db.commit()
            db.refresh(db_user)
            logger.info(f"تم إنشاء حساب طالب تلقائياً (بدون اتصال): {db_user.user_id}")
            return db_user
    
    raise HTTPException(
        status_code=401,
        detail="بيانات تسجيل الدخول غير صحيحة"
    )

async def login_for_access_token(db: AsyncSession, identifier: str, password: str, allow_demo: bool = False) -> Token:
    """تسجيل الدخول وإنشاء رمز وصول JWT."""
    result = await authenticate_user(db, identifier, password, allow_demo)
    
    # إذا كان الوضع التجريبي
    if isinstance(result, dict) and result.get("is_demo"):
        access_token_expires = timedelta(minutes=30)
        access_token = create_access_token(
            data={"sub": result["user_id"], "demo": True}, 
            expires_delta=access_token_expires
        )
        return Token(
            access_token=access_token, 
            token_type="bearer", 
            user_id=result["user_id"], 
            role=result["role"],
            is_demo=True
        )
    
    # تسجيل الدخول العادي
    user = result
    access_token_expires = timedelta(minutes=30)
    access_token = create_access_token(
        data={"sub": user.user_id, "demo": False}, 
        expires_delta=access_token_expires
    )
    return Token(
        access_token=access_token, 
        token_type="bearer", 
        user_id=user.user_id, 
        role=user.role,
        is_demo=False
    )

async def get_user_by_id(db: AsyncSession, user_id: str):
    """الحصول على معلومات المستخدم باستخدام معرف المستخدم."""
    result = await db.execute(select(User).filter(User.user_id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"user_id": user.user_id, "full_name": user.full_name, "email": user.email, "role": user.role}

async def get_user_progress_records(db: AsyncSession, user_id: str):
    """الحصول على سجلات تقدم المستخدم."""
    result = await db.execute(select(ProgressRecord).filter(ProgressRecord.user_id == user_id))
    records = result.scalars().all()
    return [
        {
            "course_code": r.course_code,
            "grade": r.grade,
            "hours": r.hours,
            "semester": r.semester,
        }
        for r in records
    ]

async def sync_student_data_from_university(db_users: AsyncSession, db_progress: AsyncSession, user_id: str, password: str) -> Dict[str, Any]:
    """
    جمع بيانات الطالب من النظام الجامعي وحفظها في قاعدة البيانات.
    
    Args:
        db_users: جلسة قاعدة بيانات المستخدمين
        db_progress: جلسة قاعدة بيانات التقدم
        user_id: الرقم الجامعي
        password: كلمة سر النظام الجامعي
        
    Returns:
        قاموس يحتوي على نتيجة العملية
    """
    try:
        # إنشاء خدمة النظام الجامعي وجمع البيانات
        university_service = None
        try:
            university_service = UniversitySystemService()
            data = university_service.collect_all_student_data(user_id, password)
        except Exception as e:
            logger.error(f"❌ خطأ في collect_all_student_data: {str(e)}", exc_info=True)
            if university_service:
                university_service.close()
            return {
                'success': False,
                'error': f'خطأ في الاتصال بالنظام الجامعي: {str(e)}'
            }
        finally:
            if university_service:
                university_service.close()
        
        if not data.get('success'):
            error_msg = data.get('error', 'فشل جمع البيانات من النظام الجامعي')
            logger.warning(f"⚠️ فشل جمع البيانات: {error_msg}")
            
            # رسالة خطأ أكثر وضوحاً للمستخدم
            user_friendly_error = error_msg
            if '419' in error_msg or 'CSRF' in error_msg:
                user_friendly_error = "فشل تسجيل الدخول إلى النظام الجامعي. يرجى المحاولة مرة أخرى بعد قليل."
            elif 'فشل تسجيل الدخول' in error_msg:
                user_friendly_error = "فشل تسجيل الدخول إلى النظام الجامعي. تأكد من صحة الرقم الجامعي وكلمة المرور."
            
            return {
                'success': False,
                'error': user_friendly_error
            }
        
        # حفظ معلومات الطالب الأكاديمية
        result = await db_progress.execute(select(StudentAcademicInfo).filter(StudentAcademicInfo.user_id == user_id))
        academic_info = result.scalar_one_or_none()
        
        grades_status = data.get('grades_status', {})
        if academic_info:
            academic_info.gpa = grades_status.get('gpa')
            academic_info.completed_hours = grades_status.get('completed_hours')
            academic_info.total_hours = grades_status.get('total_hours')
            academic_info.remaining_hours = grades_status.get('remaining_hours')
            academic_info.academic_status = grades_status.get('status')
            academic_info.raw_data = data
            academic_info.updated_at = datetime.utcnow()
        else:
            academic_info = StudentAcademicInfo(
                user_id=user_id,
                gpa=grades_status.get('gpa'),
                completed_hours=grades_status.get('completed_hours'),
                total_hours=grades_status.get('total_hours'),
                remaining_hours=grades_status.get('remaining_hours'),
                academic_status=grades_status.get('status'),
                raw_data=data
            )
            db_progress.add(academic_info)
        
        # حفظ المقررات المكتملة من جميع الفصول
        all_semesters = data.get('all_semesters_transcript', {})
        current_semester = data.get('current_semester_transcript', [])
        
        # معالجة المقررات من الفصل الحالي
        if current_semester:
            for course in current_semester:
                # محاولة استخراج معلومات المقرر
                course_code = course.get('course_code') or course.get('رمز المقرر') or course.get('المقرر', '')
                grade = course.get('grade') or course.get('الدرجة') or course.get('العلامة', '')
                hours = course.get('hours') or course.get('الساعات') or course.get('ساعات', 0)
                course_name = course.get('course_name') or course.get('اسم المقرر') or course.get('المقرر', '')
                
                if course_code and grade:
                    try:
                        hours = int(hours) if isinstance(hours, (int, str)) and str(hours).isdigit() else 0
                    except:
                        hours = 0
                    
                    # البحث عن السجل الموجود أو إنشاء جديد
                    result = await db_progress.execute(select(ProgressRecord).filter(
                        ProgressRecord.user_id == user_id,
                        ProgressRecord.course_code == course_code
                    ))
                    record = result.scalar_one_or_none()
                    
                    if record:
                        record.grade = grade
                        record.hours = hours
                        record.course_name = course_name
                        record.updated_at = datetime.utcnow()
                    else:
                        record = ProgressRecord(
                            user_id=user_id,
                            course_code=course_code,
                            grade=grade,
                            hours=hours,
                            course_name=course_name,
                            semester='current'
                        )
                        db_progress.add(record)
        
        # معالجة المقررات من جميع الفصول
        for semester_name, courses in all_semesters.items():
            for course in courses:
                course_code = course.get('course_code') or course.get('رمز المقرر') or course.get('المقرر', '')
                grade = course.get('grade') or course.get('الدرجة') or course.get('العلامة', '')
                hours = course.get('hours') or course.get('الساعات') or course.get('ساعات', 0)
                course_name = course.get('course_name') or course.get('اسم المقرر') or course.get('المقرر', '')
                
                if course_code and grade:
                    try:
                        hours = int(hours) if isinstance(hours, (int, str)) and str(hours).isdigit() else 0
                    except:
                        hours = 0
                    
                    result = await db_progress.execute(select(ProgressRecord).filter(
                        ProgressRecord.user_id == user_id,
                        ProgressRecord.course_code == course_code
                    ))
                    record = result.scalar_one_or_none()
                    
                    if record:
                        record.grade = grade
                        record.hours = hours
                        record.course_name = course_name
                        record.semester = semester_name
                        record.updated_at = datetime.utcnow()
                    else:
                        record = ProgressRecord(
                            user_id=user_id,
                            course_code=course_code,
                            grade=grade,
                            hours=hours,
                            course_name=course_name,
                            semester=semester_name
                        )
                        db_progress.add(record)
        
        # حفظ المقررات المتبقية
        remaining_courses = data.get('remaining_courses', [])
        # حذف المقررات المتبقية القديمة
        await db_progress.execute(delete(RemainingCourse).filter(RemainingCourse.user_id == user_id))
        
        for course in remaining_courses:
            course_code = course.get('course_code') or course.get('رمز المقرر') or course.get('المقرر', '')
            course_name = course.get('course_name') or course.get('اسم المقرر') or course.get('المقرر', '')
            hours = course.get('hours') or course.get('الساعات') or course.get('ساعات', 0)
            prerequisites = course.get('prerequisites') or course.get('المتطلبات', '')
            
            if course_code:
                try:
                    hours = int(hours) if isinstance(hours, (int, str)) and str(hours).isdigit() else 0
                except:
                    hours = 0
                
                remaining = RemainingCourse(
                    user_id=user_id,
                    course_code=course_code,
                    course_name=course_name,
                    hours=hours,
                    prerequisites=prerequisites,
                    raw_data=course
                )
                db_progress.add(remaining)
        
        # تحديث وقت آخر مزامنة
        result = await db_users.execute(select(User).filter(User.user_id == user_id))
        user = result.scalar_one_or_none()
        if user:
            user.last_data_sync = datetime.utcnow()
        
        await db_progress.commit()
        await db_users.commit()
        
        return {
            'success': True,
            'message': 'تم جمع البيانات بنجاح',
            'data': {
                'gpa': academic_info.gpa,
                'completed_hours': academic_info.completed_hours,
                'courses_count': len(current_semester) + sum(len(courses) for courses in all_semesters.values()),
                'remaining_courses_count': len(remaining_courses)
            }
        }
        
    except Exception as e:
        logger.error(f"خطأ في جمع بيانات الطالب {user_id}: {str(e)}", exc_info=True)
        await db_progress.rollback()
        await db_users.rollback()
        return {
            'success': False,
            'error': f'خطأ في جمع البيانات: {str(e)}'
        }
