"""
Bulk CSV Importer Service
=========================
Enhanced bulk import for 3500+ students from multiple CSV files

خدمة استيراد CSV بالجملة المحسّنة
==================================
استيراد محسّن بالجملة لـ 3500+ طالب من ملفات CSV متعددة
"""

import os
import glob
import logging
import pandas as pd
from typing import Dict, Any, List, Optional
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from database import User, ProgressRecord
from security import get_password_hash

logger = logging.getLogger("BULK_CSV_IMPORTER")


class BulkCSVImporter:
    """
    Bulk CSV Importer for student data
    مستورد CSV بالجملة لبيانات الطلاب
    
    Handles importing 3500+ students from multiple CSV files
    Each student has their own CSV file with all their data
    """
    
    def __init__(self, session: AsyncSession):
        """
        Initialize Bulk CSV Importer
        
        تهيئة مستورد CSV بالجملة
        
        Args:
            session: Database session / جلسة قاعدة البيانات
        """
        self.session = session
    
    async def import_students_bulk(
        self,
        csv_folder_path: str,
        batch_size: int = 100
    ) -> Dict[str, Any]:
        """
        Import 3500+ students from multiple CSV files
        
        استيراد 3500+ طالب من ملفات CSV متعددة
        
        Each student has their own CSV file with all their data
        كل طالب له ملف CSV خاص به يحتوي على كل بياناته
        
        Args:
            csv_folder_path: Path to folder containing CSV files
                           / مسار المجلد الذي يحتوي على ملفات CSV
            batch_size: Number of students to process per batch
                       / عدد الطلاب للمعالجة في كل دفعة
        
        Returns:
            Dictionary with import results / قاموس يحتوي على نتائج الاستيراد
        """
        try:
            # Get all CSV files
            csv_files = glob.glob(os.path.join(csv_folder_path, "*.csv"))
            
            if not csv_files:
                return {
                    "status": "error",
                    "message": f"No CSV files found in {csv_folder_path}",
                    "total_files": 0,
                    "imported": 0,
                    "failed": 0,
                    "errors": []
                }
            
            logger.info(f"Found {len(csv_files)} CSV files to process")
            
            total_imported = 0
            total_failed = 0
            errors = []
            
            # Process in batches
            for i in range(0, len(csv_files), batch_size):
                batch = csv_files[i:i+batch_size]
                batch_num = i // batch_size + 1
                total_batches = (len(csv_files) + batch_size - 1) // batch_size
                
                logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} files)...")
                
                for csv_file in batch:
                    try:
                        # Read CSV
                        df = pd.read_csv(csv_file, encoding='utf-8-sig', errors='ignore')
                        
                        # Extract student data
                        student_data = self._extract_student_from_df(df, csv_file)
                        
                        # Validate
                        validated = self._validate_student_data(student_data)
                        
                        if not validated:
                            total_failed += 1
                            errors.append({
                                "file": os.path.basename(csv_file),
                                "error": "Validation failed"
                            })
                            continue
                        
                        # Import to database
                        await self._import_student(validated)
                        
                        total_imported += 1
                        
                    except Exception as e:
                        total_failed += 1
                        error_msg = str(e)
                        errors.append({
                            "file": os.path.basename(csv_file),
                            "error": error_msg
                        })
                        logger.error(f"Failed to import {csv_file}: {error_msg}")
                
                # Commit batch
                try:
                    await self.session.commit()
                    logger.info(f"Batch {batch_num} committed: {len(batch)} students processed")
                except Exception as e:
                    await self.session.rollback()
                    logger.error(f"Error committing batch {batch_num}: {e}")
            
            return {
                "status": "success" if total_failed == 0 else "partial",
                "total_files": len(csv_files),
                "imported": total_imported,
                "failed": total_failed,
                "errors": errors[:100]  # Limit to first 100 errors
            }
            
        except Exception as e:
            logger.error(f"Error in bulk import: {e}", exc_info=True)
            return {
                "status": "error",
                "message": str(e),
                "total_files": 0,
                "imported": 0,
                "failed": 0,
                "errors": []
            }
    
    def _extract_student_from_df(self, df: pd.DataFrame, csv_file: str) -> Dict[str, Any]:
        """
        Extract student data from DataFrame
        
        استخراج بيانات الطالب من DataFrame
        
        Args:
            df: DataFrame from CSV / DataFrame من CSV
            csv_file: CSV file path / مسار ملف CSV
        
        Returns:
            Dictionary with student data / قاموس يحتوي على بيانات الطالب
        """
        # Try to infer student_id from filename (e.g., "12345.csv" -> student_id = "12345")
        filename = Path(csv_file).stem
        student_id = filename
        
        # Common column name variations
        id_columns = ['student_id', 'user_id', 'id', 'رقم_الطالب', 'الرقم_الجامعي', 'student_number']
        name_columns = ['full_name', 'name', 'student_name', 'الاسم', 'اسم_الطالب']
        email_columns = ['email', 'e_mail', 'البريد_الإلكتروني']
        major_columns = ['major', 'specialization', 'التخصص', 'الكلية']
        year_columns = ['enrollment_year', 'year', 'سنة_الالتحاق', 'العام']
        
        student_data = {
            "user_id": student_id,
            "full_name": None,
            "email": None,
            "major": None,
            "enrollment_year": None,
            "progress_records": []
        }
        
        # Extract basic info
        for col in df.columns:
            col_lower = col.lower().strip()
            
            # Name
            if any(name_col in col_lower for name_col in name_columns):
                student_data["full_name"] = str(df[col].iloc[0]) if len(df) > 0 else None
            
            # Email
            elif any(email_col in col_lower for email_col in email_columns):
                student_data["email"] = str(df[col].iloc[0]) if len(df) > 0 else None
            
            # Major
            elif any(major_col in col_lower for major_col in major_columns):
                student_data["major"] = str(df[col].iloc[0]) if len(df) > 0 else None
            
            # Enrollment year
            elif any(year_col in col_lower for year_col in year_columns):
                year_val = df[col].iloc[0] if len(df) > 0 else None
                if year_val:
                    try:
                        student_data["enrollment_year"] = int(year_val)
                    except (ValueError, TypeError):
                        pass
        
        # Extract progress records (courses and grades)
        course_columns = ['course_code', 'course', 'مقرر', 'رمز_المقرر', 'code']
        grade_columns = ['grade', 'mark', 'درجة', 'تقدير']
        hours_columns = ['hours', 'credits', 'ساعات', 'الساعات_المعتمدة']
        semester_columns = ['semester', 'term', 'فصل', 'الفصل_الدراسي']
        
        progress_records = []
        
        for _, row in df.iterrows():
            course_code = None
            grade = None
            hours = None
            semester = None
            
            for col in df.columns:
                col_lower = col.lower().strip()
                value = row[col]
                
                if pd.isna(value):
                    continue
                
                # Course code
                if any(course_col in col_lower for course_col in course_columns):
                    course_code = str(value).strip().upper()
                
                # Grade
                elif any(grade_col in col_lower for grade_col in grade_columns):
                    grade = str(value).strip().upper()
                
                # Hours
                elif any(hours_col in col_lower for hours_col in hours_columns):
                    try:
                        hours = int(value)
                    except (ValueError, TypeError):
                        pass
                
                # Semester
                elif any(sem_col in col_lower for sem_col in semester_columns):
                    semester = str(value).strip()
            
            # Create progress record if we have course code
            if course_code:
                progress_records.append({
                    "course_code": course_code,
                    "grade": grade,
                    "hours": hours,
                    "semester": semester
                })
        
        student_data["progress_records"] = progress_records
        
        return student_data
    
    def _validate_student_data(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Validate and clean student data
        
        التحقق من بيانات الطالب وتنظيفها
        
        Args:
            data: Student data dictionary / قاموس بيانات الطالب
        
        Returns:
            Validated data or None if invalid / البيانات المصدقة أو None إذا كانت غير صالحة
        """
        # Required fields
        if not data.get("user_id"):
            return None
        
        # Clean and validate
        validated = {
            "user_id": str(data["user_id"]).strip(),
            "full_name": str(data.get("full_name", "")).strip() or f"Student {data['user_id']}",
            "email": str(data.get("email", "")).strip() or None,
            "major": str(data.get("major", "")).strip() or None,
            "enrollment_year": data.get("enrollment_year"),
            "progress_records": []
        }
        
        # Validate progress records
        for record in data.get("progress_records", []):
            if record.get("course_code"):
                validated["progress_records"].append({
                    "course_code": str(record["course_code"]).strip().upper(),
                    "grade": str(record.get("grade", "")).strip().upper() if record.get("grade") else None,
                    "hours": record.get("hours"),
                    "semester": str(record.get("semester", "")).strip() if record.get("semester") else None
                })
        
        return validated
    
    async def _import_student(self, student_data: Dict[str, Any]) -> User:
        """
        Import a single student to database
        
        استيراد طالب واحد إلى قاعدة البيانات
        
        Args:
            student_data: Validated student data / بيانات الطالب المصدقة
        
        Returns:
            Created User object / كائن User المنشأ
        """
        # Check if user already exists
        from sqlalchemy import select
        stmt = select(User).where(User.user_id == student_data["user_id"])
        result = await self.session.execute(stmt)
        existing_user = result.scalar_one_or_none()
        
        if existing_user:
            # Update existing user
            existing_user.full_name = student_data["full_name"]
            if student_data.get("email"):
                existing_user.email = student_data["email"]
            
            user = existing_user
        else:
            # Create new user
            # Generate default password hash (student should change it)
            default_password = "changeme123"  # Should be changed by student
            hashed_password = get_password_hash(default_password)
            
            user = User(
                user_id=student_data["user_id"],
                full_name=student_data["full_name"],
                email=student_data.get("email"),
                hashed_password=hashed_password,
                role="student"
            )
            
            self.session.add(user)
        
        # Import progress records
        for record_data in student_data.get("progress_records", []):
            # Check if record already exists
            stmt = select(ProgressRecord).where(
                and_(
                    ProgressRecord.user_id == student_data["user_id"],
                    ProgressRecord.course_code == record_data["course_code"]
                )
            )
            result = await self.session.execute(stmt)
            existing_record = result.scalar_one_or_none()
            
            if not existing_record:
                progress_record = ProgressRecord(
                    user_id=student_data["user_id"],
                    course_code=record_data["course_code"],
                    grade=record_data.get("grade"),
                    hours=record_data.get("hours"),
                    semester=record_data.get("semester")
                )
                
                self.session.add(progress_record)
        
        return user
