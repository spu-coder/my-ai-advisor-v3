"""
Peer Matching Service
====================
AI-driven peer matching for study groups and projects

مطابقة الأقران المدفوعة بالذكاء الاصطناعي
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from database import PeerMatch, StudyGroup, User, ProgressRecord

logger = logging.getLogger("PEER_MATCHING_SERVICE")


class PeerMatchingService:
    """
    Match students for study groups and projects
    مطابقة الطلاب لمجموعات الدراسة والمشاريع
    
    This service implements intelligent peer matching based on:
    - Learning styles (FSLSM)
    - Academic performance (GPA)
    - Skills and interests
    - Course enrollment
    
    تطبق هذه الخدمة مطابقة الأقران الذكية بناءً على:
    - أساليب التعلم (FSLSM)
    - الأداء الأكاديمي (المعدل التراكمي)
    - المهارات والاهتمامات
    - التسجيل في المقررات
    """
    
    def __init__(self, session: AsyncSession):
        """
        Initialize Peer Matching Service
        
        تهيئة خدمة مطابقة الأقران
        
        Args:
            session: Database session / جلسة قاعدة البيانات
        """
        self.session = session
    
    async def find_study_partners(
        self,
        student_id: str,
        course_code: Optional[str] = None,
        match_type: str = "homogeneous",  # or "heterogeneous"
        max_matches: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Find suitable study partners
        
        العثور على شركاء دراسة مناسبين
        
        Args:
            student_id: Student user ID / معرف الطالب
            course_code: Optional course code to filter by / رمز المقرر الاختياري للتصفية
            match_type: 
                - homogeneous: similar learning styles (for review)
                - heterogeneous: complementary skills (for projects)
            max_matches: Maximum number of matches to return / الحد الأقصى لعدد المطابقات
        
        Returns:
            List of match dictionaries / قائمة قواميس المطابقات
        """
        try:
            # Get target student profile
            target = await self._get_student_profile(student_id)
            
            if not target:
                logger.warning(f"Student {student_id} not found")
                return []
            
            # Get potential matches (enrolled in same course or all students)
            candidates = await self._get_candidate_students(
                student_id=student_id,
                course_code=course_code
            )
            
            if not candidates:
                logger.info(f"No candidates found for student {student_id}")
                return []
            
            # Calculate compatibility for each candidate
            matches = []
            
            for candidate in candidates:
                score = await self._calculate_compatibility(
                    target,
                    candidate,
                    match_type=match_type
                )
                
                match_reason = self._explain_match(target, candidate, match_type)
                
                matches.append({
                    "student_id": candidate["user_id"],
                    "student_name": candidate["full_name"],
                    "compatibility_score": score,
                    "match_reason": match_reason,
                    "learning_style": candidate.get("fslsm_profile"),
                    "gpa": candidate.get("gpa")
                })
            
            # Sort by compatibility score
            matches.sort(key=lambda x: x["compatibility_score"], reverse=True)
            
            # Return top matches
            top_matches = matches[:max_matches]
            
            # Save matches to database
            for match in top_matches:
                await self._save_match(
                    student_1_id=student_id,
                    student_2_id=match["student_id"],
                    match_type=match_type,
                    compatibility_score=match["compatibility_score"],
                    match_reason=match["match_reason"],
                    course_code=course_code
                )
            
            logger.info(f"Found {len(top_matches)} matches for student {student_id}")
            
            return top_matches
            
        except Exception as e:
            logger.error(f"Error finding study partners for {student_id}: {e}", exc_info=True)
            return []
    
    async def _get_student_profile(self, student_id: str) -> Optional[Dict[str, Any]]:
        """
        Get comprehensive student profile
        
        الحصول على ملف الطالب الشامل
        
        Args:
            student_id: Student user ID / معرف الطالب
        
        Returns:
            Dictionary with student profile / قاموس يحتوي على ملف الطالب
        """
        try:
            stmt = select(User).where(User.user_id == student_id)
            result = await self.session.execute(stmt)
            student = result.scalar_one_or_none()
            
            if not student:
                return None
            
            # Get GPA from progress records
            gpa = await self._calculate_gpa(student_id)
            
            return {
                "user_id": student.user_id,
                "full_name": student.full_name,
                "fslsm_profile": student.fslsm_profile or {},
                "gpa": gpa,
                "role": student.role
            }
            
        except Exception as e:
            logger.error(f"Error getting student profile for {student_id}: {e}", exc_info=True)
            return None
    
    async def _get_candidate_students(
        self,
        student_id: str,
        course_code: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get candidate students for matching
        
        الحصول على الطلاب المرشحين للمطابقة
        
        Args:
            student_id: Student user ID to exclude / معرف الطالب للاستثناء
            course_code: Optional course code filter / مرشح رمز المقرر الاختياري
        
        Returns:
            List of candidate student profiles / قائمة ملفات الطلاب المرشحين
        """
        try:
            # Base query - exclude self
            stmt = select(User).where(
                and_(
                    User.user_id != student_id,
                    User.role == "student"
                )
            )
            
            result = await self.session.execute(stmt)
            all_students = result.scalars().all()
            
            candidates = []
            
            for student in all_students:
                # If course_code specified, check if student is enrolled
                if course_code:
                    enrolled = await self._is_student_enrolled(student.user_id, course_code)
                    if not enrolled:
                        continue
                
                # Get student profile
                gpa = await self._calculate_gpa(student.user_id)
                
                candidates.append({
                    "user_id": student.user_id,
                    "full_name": student.full_name,
                    "fslsm_profile": student.fslsm_profile or {},
                    "gpa": gpa
                })
            
            return candidates
            
        except Exception as e:
            logger.error(f"Error getting candidate students: {e}", exc_info=True)
            return []
    
    async def _calculate_compatibility(
        self,
        student_a: Dict[str, Any],
        student_b: Dict[str, Any],
        match_type: str
    ) -> float:
        """
        Calculate compatibility score (0-1)
        
        حساب درجة التوافق (0-1)
        
        Args:
            student_a: First student profile / ملف الطالب الأول
            student_b: Second student profile / ملف الطالب الثاني
            match_type: "homogeneous" or "heterogeneous" / "متشابه" أو "متكامل"
        
        Returns:
            Compatibility score between 0 and 1 / درجة التوافق بين 0 و 1
        """
        if match_type == "homogeneous":
            # Similar learning styles for effective peer review
            style_sim = self._compare_learning_styles(
                student_a.get("fslsm_profile", {}),
                student_b.get("fslsm_profile", {})
            )
            
            # Similar GPA (for effective peer review)
            gpa_a = student_a.get("gpa", 0.0) or 0.0
            gpa_b = student_b.get("gpa", 0.0) or 0.0
            
            if gpa_a > 0 and gpa_b > 0:
                gpa_sim = 1.0 - abs(gpa_a - gpa_b) / 4.0  # Normalize to 0-1
                gpa_sim = max(0.0, gpa_sim)
            else:
                gpa_sim = 0.5  # Default if GPA unavailable
            
            # Combined score (weighted)
            return 0.7 * style_sim + 0.3 * gpa_sim
        
        else:  # heterogeneous
            # Complementary skills for project work
            # Diverse learning styles (good for projects)
            style_div = 1.0 - self._compare_learning_styles(
                student_a.get("fslsm_profile", {}),
                student_b.get("fslsm_profile", {})
            )
            
            # Complementary GPA (different levels can work together)
            gpa_a = student_a.get("gpa", 0.0) or 0.0
            gpa_b = student_b.get("gpa", 0.0) or 0.0
            
            if gpa_a > 0 and gpa_b > 0:
                # Some diversity is good, but not too much
                gpa_diff = abs(gpa_a - gpa_b)
                gpa_comp = 1.0 - (gpa_diff / 4.0) if gpa_diff < 2.0 else 0.3
            else:
                gpa_comp = 0.5
            
            return 0.6 * style_div + 0.4 * gpa_comp
    
    def _compare_learning_styles(
        self,
        style_a: Dict[str, str],
        style_b: Dict[str, str]
    ) -> float:
        """
        Calculate learning style similarity (0-1)
        
        حساب تشابه أسلوب التعلم (0-1)
        
        Args:
            style_a: First student's FSLSM profile / ملف FSLSM للطالب الأول
            style_b: Second student's FSLSM profile / ملف FSLSM للطالب الثاني
        
        Returns:
            Similarity score between 0 and 1 / درجة التشابه بين 0 و 1
        """
        if not style_a or not style_b:
            return 0.5  # Default if no data
        
        # Count matching dimensions
        dimensions = ["processing", "perception", "input", "understanding"]
        matches = sum(
            1 for dim in dimensions
            if style_a.get(dim) and style_b.get(dim) and style_a.get(dim) == style_b.get(dim)
        )
        
        return matches / len(dimensions)
    
    def _explain_match(
        self,
        student_a: Dict[str, Any],
        student_b: Dict[str, Any],
        match_type: str
    ) -> str:
        """
        Generate human-readable match explanation
        
        توليد شرح مقروء للمطابقة
        
        Args:
            student_a: First student profile / ملف الطالب الأول
            student_b: Second student profile / ملف الطالب الثاني
            match_type: Match type / نوع المطابقة
        
        Returns:
            Explanation string / سلسلة الشرح
        """
        if match_type == "homogeneous":
            style_a = student_a.get("fslsm_profile", {})
            style_b = student_b.get("fslsm_profile", {})
            
            processing = style_a.get("processing") or "unknown"
            
            return (
                f"كلاكما من المتعلمين {self._translate_style(processing)}. "
                f"معدلاتكم متقاربة. مثالي للمراجعة الجماعية."
            )
        else:
            return (
                f"مهارات متكاملة: {student_a.get('full_name')} و {student_b.get('full_name')} "
                f"لديهما أساليب تعلم متنوعة. مثالي للعمل على المشاريع."
            )
    
    def _translate_style(self, style: str) -> str:
        """Translate FSLSM style to Arabic / ترجمة أسلوب FSLSM إلى العربية"""
        translations = {
            "active": "النشط",
            "reflective": "التأملي",
            "sensing": "الحسي",
            "intuitive": "الحدسي",
            "visual": "البصري",
            "verbal": "اللفظي",
            "sequential": "المتسلسل",
            "global": "الشامل"
        }
        return translations.get(style, style)
    
    async def _is_student_enrolled(self, student_id: str, course_code: str) -> bool:
        """
        Check if student is enrolled in course
        
        التحقق من تسجيل الطالب في المقرر
        
        Args:
            student_id: Student user ID / معرف الطالب
            course_code: Course code / رمز المقرر
        
        Returns:
            True if enrolled, False otherwise / True إذا كان مسجلاً، False خلاف ذلك
        """
        try:
            # Check progress records (completed or in progress)
            stmt = select(ProgressRecord).where(
                and_(
                    ProgressRecord.user_id == student_id,
                    ProgressRecord.course_code == course_code
                )
            ).limit(1)
            
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none() is not None
            
        except Exception as e:
            logger.warning(f"Error checking enrollment: {e}")
            return False
    
    async def _calculate_gpa(self, student_id: str) -> Optional[float]:
        """
        Calculate student GPA
        
        حساب المعدل التراكمي للطالب
        
        Args:
            student_id: Student user ID / معرف الطالب
        
        Returns:
            GPA value or None / قيمة المعدل التراكمي أو None
        """
        try:
            stmt = select(ProgressRecord).where(ProgressRecord.user_id == student_id)
            result = await self.session.execute(stmt)
            records = result.scalars().all()
            
            if not records:
                return None
            
            # Grade to points mapping
            grade_points = {
                "A+": 4.0, "A": 4.0, "A-": 3.7,
                "B+": 3.3, "B": 3.0, "B-": 2.7,
                "C+": 2.3, "C": 2.0, "C-": 1.7,
                "D+": 1.3, "D": 1.0, "F": 0.0
            }
            
            total_points = 0.0
            total_hours = 0
            
            for record in records:
                grade = record.grade.upper() if record.grade else None
                hours = record.hours or 0
                
                if grade and grade in grade_points and hours > 0:
                    points = grade_points[grade]
                    total_points += points * hours
                    total_hours += hours
            
            if total_hours > 0:
                return total_points / total_hours
            
            return None
            
        except Exception as e:
            logger.warning(f"Error calculating GPA for {student_id}: {e}")
            return None
    
    async def _save_match(
        self,
        student_1_id: str,
        student_2_id: str,
        match_type: str,
        compatibility_score: float,
        match_reason: str,
        course_code: Optional[str] = None
    ) -> PeerMatch:
        """
        Save match to database
        
        حفظ المطابقة في قاعدة البيانات
        
        Args:
            student_1_id: First student ID / معرف الطالب الأول
            student_2_id: Second student ID / معرف الطالب الثاني
            match_type: Match type / نوع المطابقة
            compatibility_score: Compatibility score / درجة التوافق
            match_reason: Match reason / سبب المطابقة
            course_code: Optional course code / رمز المقرر الاختياري
        
        Returns:
            Created PeerMatch object / كائن PeerMatch المنشأ
        """
        try:
            # Check if match already exists
            stmt = select(PeerMatch).where(
                and_(
                    or_(
                        and_(PeerMatch.student_1_id == student_1_id, PeerMatch.student_2_id == student_2_id),
                        and_(PeerMatch.student_1_id == student_2_id, PeerMatch.student_2_id == student_1_id)
                    ),
                    PeerMatch.match_type == match_type
                )
            )
            
            result = await self.session.execute(stmt)
            existing_match = result.scalar_one_or_none()
            
            if existing_match:
                # Update existing match
                existing_match.compatibility_score = compatibility_score
                existing_match.match_reason = match_reason
                existing_match.updated_at = datetime.utcnow()
                
                await self.session.commit()
                await self.session.refresh(existing_match)
                
                return existing_match
            
            # Create new match
            match = PeerMatch(
                student_1_id=student_1_id,
                student_2_id=student_2_id,
                match_type=match_type,
                compatibility_score=compatibility_score,
                match_reason=match_reason,
                course_code=course_code,
                status="suggested"
            )
            
            self.session.add(match)
            await self.session.commit()
            await self.session.refresh(match)
            
            return match
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error saving match: {e}", exc_info=True)
            raise
    
    async def create_study_group(
        self,
        course_code: str,
        group_type: str,
        member_ids: List[str],
        max_size: int = 5,
        description: Optional[str] = None
    ) -> StudyGroup:
        """
        Create a study group from matched students
        
        إنشاء مجموعة دراسة من الطلاب المطابقين
        
        Args:
            course_code: Course code / رمز المقرر
            group_type: "homogeneous" or "heterogeneous" / "متشابه" أو "متكامل"
            member_ids: List of student IDs / قائمة معرفات الطلاب
            max_size: Maximum group size / الحد الأقصى لحجم المجموعة
            description: Optional group description / وصف المجموعة الاختياري
        
        Returns:
            Created StudyGroup object / كائن StudyGroup المنشأ
        """
        try:
            # Prepare members data
            members = []
            for student_id in member_ids:
                members.append({
                    "student_id": student_id,
                    "role": "member",
                    "joined_at": datetime.utcnow().isoformat()
                })
            
            group = StudyGroup(
                course_code=course_code,
                group_type=group_type,
                max_size=max_size,
                current_size=len(member_ids),
                members=members,
                description=description
            )
            
            self.session.add(group)
            await self.session.commit()
            await self.session.refresh(group)
            
            logger.info(f"Created study group {group.id} with {len(member_ids)} members")
            
            return group
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error creating study group: {e}", exc_info=True)
            raise
    
    async def get_student_matches(
        self,
        student_id: str,
        status: Optional[str] = None
    ) -> List[PeerMatch]:
        """
        Get all matches for a student
        
        الحصول على جميع المطابقات لطالب
        
        Args:
            student_id: Student user ID / معرف الطالب
            status: Optional status filter / مرشح الحالة الاختياري
        
        Returns:
            List of PeerMatch objects / قائمة كائنات PeerMatch
        """
        try:
            stmt = select(PeerMatch).where(
                or_(
                    PeerMatch.student_1_id == student_id,
                    PeerMatch.student_2_id == student_id
                )
            )
            
            if status:
                stmt = stmt.where(PeerMatch.status == status)
            
            stmt = stmt.order_by(PeerMatch.compatibility_score.desc(), PeerMatch.created_at.desc())
            
            result = await self.session.execute(stmt)
            return list(result.scalars().all())
            
        except Exception as e:
            logger.error(f"Error getting matches for {student_id}: {e}", exc_info=True)
            return []
