"""
Progress Service Module
=======================
This module handles student academic progress tracking and analysis:
- Recording completed courses
- GPA calculation and analysis
- Remaining courses identification
- GPA simulation

وحدة خدمة التقدم
================
هذه الوحدة تتعامل مع تتبع وتحليل التقدم الأكاديمي للطلاب:
- تسجيل المقررات المكتملة
- حساب وتحليل المعدل التراكمي
- تحديد المقررات المتبقية
- محاكاة المعدل التراكمي
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import ProgressRecord
from config_manager import get_config
from fastapi import HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

# ------------------------------------------------------------
# نماذج Pydantic
# ------------------------------------------------------------
class ProgressRecordCreate(BaseModel):
    user_id: str
    course_code: str
    grade: str
    hours: int
    semester: Optional[str] = None

class ProgressRecordInDB(ProgressRecordCreate):
    id: int
    class Config:
        orm_mode = True

class StudentRecord(BaseModel):
    completed_courses: dict[str, str] # {course_code: grade}

class GpaSimulation(BaseModel):
    current_gpa: float
    current_hours: int
    new_courses: dict[str, int] # {course_code: hours}
    expected_grades: dict[str, str] # {course_code: grade}

# ------------------------------------------------------------
# بيانات الخطة الدراسية (لأغراض المحاكاة والتحليل)
# ------------------------------------------------------------
GRADE_POINTS = get_config("gpa_scale", {})

FULL_STUDY_PLAN = {
    "total_hours": 130,
    "courses": {
        "CS101": {"name": "Intro to Programming", "hours": 3, "prereqs": []},
        "MATH101": {"name": "Calculus I", "hours": 3, "prereqs": []},
        "PHYS101": {"name": "Physics I", "hours": 4, "prereqs": []},
        "CS102": {"name": "Data Structures", "hours": 3, "prereqs": ["CS101"]},
        "CS201": {"name": "Algorithms", "hours": 3, "prereqs": ["CS102"]},
        "AI300": {"name": "Intro to AI", "hours": 3, "prereqs": ["CS102", "MATH101"]},
        "DS310": {"name": "Data Science", "hours": 3, "prereqs": ["MATH101"]},
        "NLP401": {"name": "Natural Language Processing", "hours": 3, "prereqs": ["AI300"]},
        "SEC200": {"name": "Network Security", "hours": 3, "prereqs": ["CS102"]},
    }
}

# ------------------------------------------------------------
# وظائف الخدمة
# ------------------------------------------------------------

async def record_progress(db: AsyncSession, record_data: dict):
    """تسجيل مقرر مكتمل."""
    try:
        db_record = ProgressRecord(**record_data)
        db.add(db_record)
        await db.commit()
        await db.refresh(db_record)
        return {
            "id": db_record.id,
            "user_id": db_record.user_id,
            "course_code": db_record.course_code,
            "grade": db_record.grade,
            "hours": db_record.hours,
            "semester": db_record.semester
        }
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=f"Error recording progress: {str(e)}")

async def get_student_progress(db: AsyncSession, user_id: str) -> List[ProgressRecord]:
    result = await db.execute(select(ProgressRecord).filter(ProgressRecord.user_id == user_id))
    return result.scalars().all()

async def analyze_progress(db_progress: AsyncSession, db_users: AsyncSession, user_id: str) -> Dict[str, Any]:
    """تحليل التقدم الأكاديمي للمستخدم."""
    try:
        records = await get_student_progress(db_progress, user_id)
        completed_courses = {r.course_code: r.grade for r in records}
        
        completed_set = set(completed_courses.keys())
        all_courses_set = set(FULL_STUDY_PLAN["courses"].keys())
        remaining_courses = list(all_courses_set - completed_set)

        total_points = 0
        total_hours = 0
        for code, grade in completed_courses.items():
            grade = grade.upper()
            if code in FULL_STUDY_PLAN["courses"] and grade in GRADE_POINTS:
                hours = FULL_STUDY_PLAN["courses"][code]["hours"]
                total_points += GRADE_POINTS[grade] * hours
                total_hours += hours

        gpa = total_points / total_hours if total_hours else 0.0

        registerable = []
        for code in remaining_courses:
            data = FULL_STUDY_PLAN["courses"].get(code, {})
            prereqs = data.get("prereqs", [])
            if all(p in completed_set for p in prereqs):
                registerable.append({
                    "code": code, 
                    "name": data.get("name", "Unknown"), 
                    "hours": data.get("hours", 0)
                })

        return {
            "current_gpa": round(gpa, 2),
            "completed_hours": total_hours,
            "remaining_hours": FULL_STUDY_PLAN["total_hours"] - total_hours,
            "remaining_courses_count": len(remaining_courses),
            "registerable_next_semester": registerable,
            "completed_courses": completed_courses
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error analyzing progress: {str(e)}")

def _calculate_current_metrics(records: List[ProgressRecord]) -> tuple[float, int]:
    total_points = 0.0
    total_hours = 0
    for record in records:
        grade = record.grade.upper()
        if grade in GRADE_POINTS and record.course_code in FULL_STUDY_PLAN["courses"]:
            hours = FULL_STUDY_PLAN["courses"][record.course_code]["hours"]
            total_points += GRADE_POINTS[grade] * hours
            total_hours += hours
    current_gpa = total_points / total_hours if total_hours else 0.0
    return round(current_gpa, 2), total_hours


async def simulate_gpa(db_progress: AsyncSession, user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """محاكاة المعدل التراكمي بناءً على الدرجات المتوقعة مع استخدام بيانات الطالب الفعلية."""
    try:
        records = await get_student_progress(db_progress, user_id)
        inferred_gpa, inferred_hours = _calculate_current_metrics(records)

        current_gpa = float(data.get("current_gpa") or inferred_gpa)
        current_hours = int(data.get("current_hours") or inferred_hours)
        new_courses = data.get("new_courses", {})
        expected_grades = data.get("expected_grades", {})

        if not new_courses or not expected_grades:
            raise HTTPException(status_code=400, detail="يجب تحديد المقررات والدرجات المتوقعة.")

        current_points = current_gpa * current_hours
        new_points = 0.0
        new_hours = 0

        invalid_courses = []
        for code, grade in expected_grades.items():
            grade = grade.upper()
            if code not in new_courses:
                invalid_courses.append(code)
                continue
            if grade not in GRADE_POINTS:
                invalid_courses.append(code)
                continue
            hours = new_courses[code]
            new_points += GRADE_POINTS[grade] * hours
            new_hours += hours

        if invalid_courses:
            raise HTTPException(
                status_code=400,
                detail=f"مقررات أو درجات غير صالحة في المحاكاة: {', '.join(invalid_courses)}"
            )

        total_points = current_points + new_points
        total_hours = current_hours + new_hours
        final_gpa = total_points / total_hours if total_hours > 0 else 0.0

        return {
            "current_gpa": round(current_gpa, 2),
            "future_gpa": round(final_gpa, 2),
            "total_hours_after_semester": total_hours,
            "hours_added": new_hours,
            "data_source": "db" if (data.get("current_gpa") is None or data.get("current_hours") is None) else "payload"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error simulating GPA: {str(e)}")
