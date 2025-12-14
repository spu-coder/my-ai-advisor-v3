"""
Learning Style Service - FSLSM ML Prediction
============================================
ML-based learning style prediction from behavioral data

التنبؤ بأسلوب التعلم باستخدام ML من البيانات السلوكية
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from database import User, LearningInteraction

logger = logging.getLogger("LEARNING_STYLE_SERVICE")


class LearningStyleService:
    """
    Learning Style Service with ML-based FSLSM prediction
    خدمة أسلوب التعلم مع التنبؤ بـ FSLSM القائم على ML
    
    Predicts student learning style (FSLSM) from behavioral data
    instead of relying solely on questionnaires.
    
    يتنبأ بأسلوب تعلم الطالب (FSLSM) من البيانات السلوكية
    بدلاً من الاعتماد فقط على الاستبيانات.
    """
    
    def __init__(self, session: AsyncSession):
        """
        Initialize Learning Style Service
        
        تهيئة خدمة أسلوب التعلم
        
        Args:
            session: Database session / جلسة قاعدة البيانات
        """
        self.session = session
        # Note: In production, load pre-trained ML models here
        # ملاحظة: في الإنتاج، قم بتحميل نماذج ML المدربة مسبقاً هنا
        self.models = {}  # Placeholder for ML models
    
    async def predict_learning_style(
        self,
        student_id: str,
        use_ml_prediction: bool = True
    ) -> Dict[str, Any]:
        """
        Predict learning style from behavioral data (ML-based)
        
        التنبؤ بأسلوب التعلم من البيانات السلوكية (قائم على ML)
        
        Uses behavioral features:
        - Time spent on videos vs readings
        - Forum participation rate
        - Practical vs theoretical content preference
        - Sequential vs random navigation
        
        يستخدم الميزات السلوكية:
        - الوقت المستغرق في الفيديوهات مقابل القراءات
        - معدل المشاركة في المنتديات
        - تفضيل المحتوى العملي مقابل النظري
        - التنقل المتسلسل مقابل العشوائي
        
        Args:
            student_id: Student user ID / معرف الطالب
            use_ml_prediction: Whether to use ML prediction / ما إذا كان سيتم استخدام التنبؤ بـ ML
        
        Returns:
            Dictionary with learning style prediction / قاموس يحتوي على تنبؤ أسلوب التعلم
        """
        try:
            # Get behavioral features
            features = await self._extract_behavioral_features(student_id)
            
            if not features or not use_ml_prediction:
                # Fallback to questionnaire-based (if available)
                return await self._get_questionnaire_based_style(student_id)
            
            # Predict each FSLSM dimension
            predictions = {}
            confidences = {}
            
            for dimension in ["processing", "perception", "input", "understanding"]:
                # In production, use actual ML model here
                # في الإنتاج، استخدم نموذج ML الفعلي هنا
                prediction, confidence = self._predict_dimension(features, dimension)
                
                predictions[dimension] = prediction
                confidences[dimension] = confidence
            
            # Generate recommendations
            recommendations = self._generate_recommendations(predictions)
            
            # Detect deviations (if baseline exists)
            deviations = await self._detect_style_deviations(student_id, predictions)
            
            # Update student's FSLSM profile
            await self._update_student_profile(student_id, predictions, confidences)
            
            return {
                "student_id": student_id,
                "learning_style": predictions,
                "confidence": confidences,
                "method": "ml_prediction",
                "recommendations": recommendations,
                "deviations": deviations,
                "study_strategies": self._get_study_strategies(predictions),
                "features_used": features
            }
            
        except Exception as e:
            logger.error(f"Error predicting learning style for {student_id}: {e}", exc_info=True)
            return {
                "student_id": student_id,
                "error": str(e),
                "method": "error"
            }
    
    async def _extract_behavioral_features(
        self,
        student_id: str
    ) -> Dict[str, float]:
        """
        Extract behavioral features from learning_interactions
        
        استخراج الميزات السلوكية من تفاعلات التعلم
        
        Args:
            student_id: Student user ID / معرف الطالب
        
        Returns:
            Dictionary with behavioral features / قاموس يحتوي على الميزات السلوكية
        """
        try:
            # Get interactions from last 60 days
            cutoff_date = datetime.utcnow() - timedelta(days=60)
            
            stmt = select(LearningInteraction).where(
                and_(
                    LearningInteraction.student_id == student_id,
                    LearningInteraction.timestamp >= cutoff_date
                )
            )
            
            result = await self.session.execute(stmt)
            interactions = result.scalars().all()
            
            if not interactions:
                return {}  # No data available
            
            # Calculate features
            features = {
                # Input dimension (visual vs verbal)
                "time_on_videos": 0.0,
                "time_on_readings": 0.0,
                "visual_content_preference": 0.0,
                
                # Processing dimension (active vs reflective)
                "forum_posts_count": 0,
                "group_participation_rate": 0.0,
                "solo_study_time": 0.0,
                
                # Perception dimension (sensing vs intuitive)
                "practical_examples_clicks": 0,
                "theoretical_content_time": 0.0,
                
                # Understanding dimension (sequential vs global)
                "linear_navigation_rate": 0.0,
                "jump_between_topics_rate": 0.0
            }
            
            total_time = 0.0
            video_time = 0.0
            reading_time = 0.0
            
            for interaction in interactions:
                duration = interaction.duration_seconds or 0
                total_time += duration
                
                # Input dimension
                if interaction.interaction_type == "video_view":
                    video_time += duration
                    features["time_on_videos"] += duration
                elif interaction.interaction_type == "reading":
                    reading_time += duration
                    features["time_on_readings"] += duration
                
                # Processing dimension
                if interaction.interaction_type == "forum_post":
                    features["forum_posts_count"] += 1
                elif interaction.interaction_type == "group_activity":
                    features["group_participation_rate"] += 1
                elif interaction.interaction_type == "solo_study":
                    features["solo_study_time"] += duration
                
                # Perception dimension
                if interaction.content_type == "practical":
                    features["practical_examples_clicks"] += 1
                elif interaction.content_type == "theoretical":
                    features["theoretical_content_time"] += duration
                
                # Understanding dimension (simplified - would need navigation tracking)
                # This is a placeholder - in production, track actual navigation patterns
                if interaction.metadata and interaction.metadata.get("linear_navigation"):
                    features["linear_navigation_rate"] += 1
                else:
                    features["jump_between_topics_rate"] += 1
            
            # Calculate ratios
            if total_time > 0:
                features["visual_content_preference"] = video_time / total_time
                features["solo_study_time"] = features["solo_study_time"] / total_time
                features["theoretical_content_time"] = features["theoretical_content_time"] / total_time
            
            if len(interactions) > 0:
                features["group_participation_rate"] = features["group_participation_rate"] / len(interactions)
                features["linear_navigation_rate"] = features["linear_navigation_rate"] / len(interactions)
                features["jump_between_topics_rate"] = features["jump_between_topics_rate"] / len(interactions)
            
            return features
            
        except Exception as e:
            logger.error(f"Error extracting behavioral features for {student_id}: {e}", exc_info=True)
            return {}
    
    def _predict_dimension(
        self,
        features: Dict[str, float],
        dimension: str
    ) -> tuple[str, float]:
        """
        Predict a single FSLSM dimension
        
        التنبؤ ببعد واحد من FSLSM
        
        Args:
            features: Behavioral features / الميزات السلوكية
            dimension: FSLSM dimension / بعد FSLSM
        
        Returns:
            Tuple of (prediction, confidence) / مجموعة من (التنبؤ، الثقة)
        """
        # Simplified prediction logic (placeholder for ML model)
        # منطق تنبؤ مبسط (مكان لنموذج ML)
        
        if dimension == "input":
            # Visual vs Verbal
            visual_pref = features.get("visual_content_preference", 0.5)
            if visual_pref > 0.6:
                return ("visual", 0.8)
            elif visual_pref < 0.4:
                return ("verbal", 0.8)
            else:
                return ("visual", 0.6)  # Default to visual
        
        elif dimension == "processing":
            # Active vs Reflective
            forum_posts = features.get("forum_posts_count", 0)
            group_rate = features.get("group_participation_rate", 0.0)
            
            if forum_posts > 5 or group_rate > 0.3:
                return ("active", 0.75)
            else:
                return ("reflective", 0.75)
        
        elif dimension == "perception":
            # Sensing vs Intuitive
            practical = features.get("practical_examples_clicks", 0)
            theoretical_time = features.get("theoretical_content_time", 0.0)
            
            if practical > 10 or theoretical_time < 0.3:
                return ("sensing", 0.7)
            else:
                return ("intuitive", 0.7)
        
        elif dimension == "understanding":
            # Sequential vs Global
            linear_rate = features.get("linear_navigation_rate", 0.5)
            
            if linear_rate > 0.6:
                return ("sequential", 0.7)
            else:
                return ("global", 0.7)
        
        # Default
        return ("unknown", 0.5)
    
    async def _detect_style_deviations(
        self,
        student_id: str,
        current_style: Dict[str, str]
    ) -> List[Dict[str, Any]]:
        """
        Detect deviations from established learning style
        
        كشف الانحرافات عن أسلوب التعلم المعتاد
        
        This is a CRITICAL indicator of wellness issues!
        هذا مؤشر حاسم لمشاكل العافية!
        
        Args:
            student_id: Student user ID / معرف الطالب
            current_style: Current predicted style / الأسلوب المتوقع الحالي
        
        Returns:
            List of deviation dictionaries / قائمة قواميس الانحرافات
        """
        try:
            # Get student's historical style
            stmt = select(User).where(User.user_id == student_id)
            result = await self.session.execute(stmt)
            student = result.scalar_one_or_none()
            
            if not student or not student.fslsm_profile:
                return []  # No baseline yet
            
            baseline_style = student.fslsm_profile
            deviations = []
            
            for dimension in ["processing", "perception", "input", "understanding"]:
                baseline_val = baseline_style.get(dimension)
                current_val = current_style.get(dimension)
                
                if baseline_val and current_val and baseline_val != current_val:
                    # MAJOR DEVIATION DETECTED!
                    deviations.append({
                        "dimension": dimension,
                        "baseline": baseline_val,
                        "current": current_val,
                        "severity": "high",
                        "interpretation": self._interpret_deviation(dimension, baseline_val, current_val)
                    })
            
            return deviations
            
        except Exception as e:
            logger.error(f"Error detecting style deviations for {student_id}: {e}", exc_info=True)
            return []
    
    def _interpret_deviation(
        self,
        dimension: str,
        baseline: str,
        current: str
    ) -> str:
        """
        Interpret what the deviation might indicate
        
        تفسير ما قد يشير إليه الانحراف
        
        Args:
            dimension: FSLSM dimension / بعد FSLSM
            baseline: Baseline value / القيمة الأساسية
            current: Current value / القيمة الحالية
        
        Returns:
            Interpretation string / سلسلة التفسير
        """
        interpretations = {
            ("processing", "active", "reflective"): 
                "الطالب أصبح أقل مشاركة في الأنشطة الجماعية. قد يشير إلى انسحاب اجتماعي أو إرهاق إدراكي.",
            
            ("processing", "reflective", "active"):
                "الطالب أصبح أكثر نشاطاً في المشاركة. قد يشير إلى تحسن في الثقة أو زيادة في الدافعية.",
            
            ("input", "visual", "verbal"):
                "الطالب توقف عن استخدام المواد البصرية. قد يشير إلى صعوبة في الوصول للموارد أو انخفاض في الدافعية.",
            
            ("input", "verbal", "visual"):
                "الطالب بدأ الاعتماد أكثر على المواد البصرية. قد يشير إلى تغيير في تفضيلات التعلم.",
            
            ("perception", "sensing", "intuitive"):
                "الطالب أصبح أقل اهتماماً بالأمثلة العملية. قد يشير إلى تغيير في أسلوب التعلم أو صعوبة في التركيز.",
            
            ("understanding", "sequential", "global"):
                "الطالب بدأ القفز بين المواضيع بدلاً من التعلم المتسلسل. قد يشير إلى صعوبة في التركيز أو قلق.",
        }
        
        key = (dimension, baseline, current)
        return interpretations.get(key, f"تم اكتشاف تغيير في أسلوب التعلم: {dimension} من {baseline} إلى {current}")
    
    def _generate_recommendations(
        self,
        predictions: Dict[str, str]
    ) -> List[str]:
        """
        Generate study recommendations based on learning style
        
        توليد توصيات الدراسة بناءً على أسلوب التعلم
        
        Args:
            predictions: FSLSM predictions / تنبؤات FSLSM
        
        Returns:
            List of recommendation strings / قائمة سلاسل التوصيات
        """
        recommendations = []
        
        # Processing dimension
        if predictions.get("processing") == "active":
            recommendations.append("استخدم التعلم النشط: شارك في المناقشات، اشرح المفاهيم للآخرين، استخدم التطبيق العملي")
        else:
            recommendations.append("استخدم التعلم التأملي: خذ وقتاً للتفكير، اكتب ملخصات، راجع المواد بهدوء")
        
        # Input dimension
        if predictions.get("input") == "visual":
            recommendations.append("استخدم المواد البصرية: الرسوم البيانية، الخرائط الذهنية، الفيديوهات، الصور")
        else:
            recommendations.append("استخدم المواد اللفظية: القراءة، المحاضرات، المناقشات، الشرح الشفهي")
        
        # Perception dimension
        if predictions.get("perception") == "sensing":
            recommendations.append("ركز على الأمثلة العملية والتطبيقات الواقعية")
        else:
            recommendations.append("ركز على المفاهيم النظرية والعلاقات بين الأفكار")
        
        # Understanding dimension
        if predictions.get("understanding") == "sequential":
            recommendations.append("اتبع نهجاً متسلسلاً: ادرس المواضيع بالترتيب، اربط كل موضوع بالسابق")
        else:
            recommendations.append("استخدم نهجاً شاملاً: ابدأ بنظرة عامة، ثم اربط التفاصيل بالصورة الكبيرة")
        
        return recommendations
    
    def _get_study_strategies(
        self,
        predictions: Dict[str, str]
    ) -> Dict[str, List[str]]:
        """
        Get specific study strategies for learning style
        
        الحصول على استراتيجيات دراسة محددة لأسلوب التعلم
        
        Args:
            predictions: FSLSM predictions / تنبؤات FSLSM
        
        Returns:
            Dictionary with strategies by dimension / قاموس يحتوي على الاستراتيجيات حسب البعد
        """
        strategies = {
            "processing": [],
            "input": [],
            "perception": [],
            "understanding": []
        }
        
        # Processing strategies
        if predictions.get("processing") == "active":
            strategies["processing"] = [
                "شارك في مجموعات الدراسة",
                "اشرح المفاهيم للآخرين",
                "استخدم التطبيق العملي",
                "شارك في المناقشات"
            ]
        else:
            strategies["processing"] = [
                "ادرس في بيئة هادئة",
                "اكتب ملخصات",
                "راجع المواد بهدوء",
                "خذ وقتاً للتفكير"
            ]
        
        # Input strategies
        if predictions.get("input") == "visual":
            strategies["input"] = [
                "استخدم الخرائط الذهنية",
                "شاهد الفيديوهات التعليمية",
                "استخدم الرسوم البيانية",
                "ارسم المخططات"
            ]
        else:
            strategies["input"] = [
                "اقرأ الكتب والمقالات",
                "استمع للمحاضرات",
                "شارك في المناقشات",
                "سجل الملاحظات"
            ]
        
        # Perception strategies
        if predictions.get("perception") == "sensing":
            strategies["perception"] = [
                "ركز على الأمثلة العملية",
                "استخدم التطبيقات الواقعية",
                "ربط المفاهيم بالحياة اليومية",
                "استخدم التجارب العملية"
            ]
        else:
            strategies["perception"] = [
                "ركز على المفاهيم النظرية",
                "ابحث عن العلاقات بين الأفكار",
                "استخدم النماذج والمخططات",
                "فكر في التطبيقات المستقبلية"
            ]
        
        # Understanding strategies
        if predictions.get("understanding") == "sequential":
            strategies["understanding"] = [
                "اتبع الترتيب المنطقي",
                "اربط كل موضوع بالسابق",
                "استخدم الخطوات المتسلسلة",
                "بني المعرفة تدريجياً"
            ]
        else:
            strategies["understanding"] = [
                "ابدأ بنظرة عامة",
                "اربط التفاصيل بالصورة الكبيرة",
                "استخدم الخرائط الذهنية",
                "فكر في الروابط بين المواضيع"
            ]
        
        return strategies
    
    async def _get_questionnaire_based_style(
        self,
        student_id: str
    ) -> Dict[str, Any]:
        """
        Get learning style from questionnaire (fallback)
        
        الحصول على أسلوب التعلم من الاستبيان (احتياطي)
        
        Args:
            student_id: Student user ID / معرف الطالب
        
        Returns:
            Dictionary with questionnaire-based style / قاموس يحتوي على الأسلوب القائم على الاستبيان
        """
        # Placeholder - in production, retrieve from questionnaire results
        # مكان - في الإنتاج، استرجع من نتائج الاستبيان
        return {
            "student_id": student_id,
            "learning_style": {},
            "method": "questionnaire",
            "message": "No questionnaire data available / لا توجد بيانات استبيان متاحة"
        }
    
    async def _update_student_profile(
        self,
        student_id: str,
        predictions: Dict[str, str],
        confidences: Dict[str, float]
    ) -> None:
        """
        Update student's FSLSM profile in database
        
        تحديث ملف FSLSM للطالب في قاعدة البيانات
        
        Args:
            student_id: Student user ID / معرف الطالب
            predictions: FSLSM predictions / تنبؤات FSLSM
            confidences: Confidence scores / درجات الثقة
        """
        try:
            stmt = select(User).where(User.user_id == student_id)
            result = await self.session.execute(stmt)
            student = result.scalar_one_or_none()
            
            if student:
                student.fslsm_profile = predictions
                student.fslsm_confidence = sum(confidences.values()) / len(confidences) if confidences else 0.0
                student.fslsm_predicted_at = datetime.utcnow()
                
                await self.session.commit()
                logger.info(f"Updated FSLSM profile for student {student_id}")
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error updating student profile for {student_id}: {e}", exc_info=True)
    
    async def log_interaction(
        self,
        student_id: str,
        interaction_type: str,
        duration_seconds: Optional[int] = None,
        content_type: Optional[str] = None,
        course_code: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> LearningInteraction:
        """
        Log a learning interaction
        
        تسجيل تفاعل تعلم
        
        Args:
            student_id: Student user ID / معرف الطالب
            interaction_type: Type of interaction / نوع التفاعل
            duration_seconds: Duration in seconds / المدة بالثواني
            content_type: Content type / نوع المحتوى
            course_code: Course code / رمز المقرر
            metadata: Additional metadata / بيانات وصفية إضافية
        
        Returns:
            Created LearningInteraction / تفاعل التعلم المنشأ
        """
        try:
            interaction = LearningInteraction(
                student_id=student_id,
                interaction_type=interaction_type,
                duration_seconds=duration_seconds,
                content_type=content_type,
                course_code=course_code,
                metadata=metadata
            )
            
            self.session.add(interaction)
            await self.session.commit()
            await self.session.refresh(interaction)
            
            return interaction
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error logging interaction: {e}", exc_info=True)
            raise
