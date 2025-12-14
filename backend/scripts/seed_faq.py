"""
FAQ Seed Script - Populate FAQ Database
========================================
Seed script to populate FAQ entries from real regulations

سكريبت بذر البيانات - ملء قاعدة بيانات الأسئلة الشائعة
====================================================
سكريبت لملء إدخالات الأسئلة الشائعة من اللوائح الحقيقية
"""

import asyncio
import sys
import os
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import AsyncSession
from database import AsyncSessionLocal, FAQEntry, init_db


# FAQ Data from real regulations
# بيانات الأسئلة الشائعة من اللوائح الحقيقية
FAQ_DATA = [
    {
        "question_pattern": r"(?:what|ما).*(?:passing|نجاح|نجح).*(?:grade|درجة|تقدير|mark)",
        "answer_template": "درجة النجاح الدنيا هي C (60%). بحسب دليل الطالب 2024، المادة 7، البند 3.",
        "category": "regulations",
        "priority": 1,
        "metadata": {"applies_to": "all_students", "year": 2024}
    },
    {
        "question_pattern": r"(?:what|ما).*(?:minimum|الحد الأدنى|أدنى).*(?:gpa|معدل|معدل تراكمي)",
        "answer_template": "الحد الأدنى للمعدل التراكمي للبقاء في الكلية هو 2.0 (C). المعدل الأدنى للتخرج هو 2.0.",
        "category": "regulations",
        "priority": 1,
        "metadata": {"applies_to": "all_students", "year": 2024}
    },
    {
        "question_pattern": r"(?:how|كيف).*(?:calculate|حساب).*(?:gpa|معدل|معدل تراكمي)",
        "answer_template": "يتم حساب المعدل التراكمي كالتالي: (مجموع (الدرجة × الساعات المعتمدة)) / (مجموع الساعات المعتمدة). الدرجات: A+=4.0, A=4.0, A-=3.7, B+=3.3, B=3.0, B-=2.7, C+=2.3, C=2.0, C-=1.7, D+=1.3, D=1.0, F=0.0",
        "category": "regulations",
        "priority": 2,
        "metadata": {"applies_to": "all_students"}
    },
    {
        "question_pattern": r"(?:what|ما).*(?:prerequisites|متطلبات سابقة|متطلب سابق).*(?:course|مقرر)",
        "answer_template": "المتطلبات السابقة تختلف حسب المقرر. يمكنك التحقق من المتطلبات السابقة لكل مقرر في دليل المقررات أو من خلال النظام الأكاديمي.",
        "category": "regulations",
        "priority": 2,
        "metadata": {"applies_to": "all_students"}
    },
    {
        "question_pattern": r"(?:when|متى).*(?:registration|تسجيل|التسجيل).*(?:open|يفتح|يبدأ)",
        "answer_template": "يبدأ التسجيل عادة قبل بداية الفصل الدراسي بأسبوعين. يتم الإعلان عن مواعيد التسجيل عبر البريد الإلكتروني والنظام الأكاديمي. يرجى متابعة الإعلانات الرسمية.",
        "category": "deadlines",
        "priority": 1,
        "metadata": {"applies_to": "all_students"}
    },
    {
        "question_pattern": r"(?:what|ما).*(?:maximum|الحد الأقصى|أقصى).*(?:courses|مقررات|hours|ساعات).*(?:semester|فصل)",
        "answer_template": "الحد الأقصى للساعات المعتمدة المسموح بتسجيلها في الفصل الواحد هو 18 ساعة معتمدة. يمكن للطلاب المتفوقين (معدل 3.5+) طلب تسجيل حتى 21 ساعة بموافقة العميد.",
        "category": "regulations",
        "priority": 1,
        "metadata": {"applies_to": "all_students", "year": 2024}
    },
    {
        "question_pattern": r"(?:how|كيف).*(?:withdraw|انسحاب|الانسحاب).*(?:course|مقرر)",
        "answer_template": "يمكنك الانسحاب من مقرر خلال الأسابيع الثمانية الأولى من الفصل. بعد ذلك، يُسمح بالانسحاب فقط في حالات خاصة بموافقة العميد. الانسحاب بعد الأسبوع الثامن يظهر في السجل الأكاديمي كـ 'W'.",
        "category": "regulations",
        "priority": 2,
        "metadata": {"applies_to": "all_students"}
    },
    {
        "question_pattern": r"(?:what|ما).*(?:graduation|تخرج|التخرج).*(?:requirements|متطلبات)",
        "answer_template": "متطلبات التخرج تشمل: إكمال جميع الساعات المعتمدة المطلوبة (عادة 132-140 ساعة)، الحصول على معدل تراكمي لا يقل عن 2.0، إكمال مشروع التخرج بنجاح، وإكمال متطلبات اللغة الإنجليزية والتربية الوطنية.",
        "category": "regulations",
        "priority": 1,
        "metadata": {"applies_to": "all_students"}
    },
    {
        "question_pattern": r"(?:when|متى).*(?:exam|امتحان|الامتحان|exams|امتحانات).*(?:schedule|جدول|مواعيد)",
        "answer_template": "يتم الإعلان عن جدول الامتحانات قبل نهاية الفصل الدراسي بأسبوعين على الأقل. يمكنك الاطلاع على الجدول من خلال النظام الأكاديمي أو من خلال مكتب التسجيل.",
        "category": "deadlines",
        "priority": 1,
        "metadata": {"applies_to": "all_students"}
    },
    {
        "question_pattern": r"(?:what|ما).*(?:academic|أكاديمي).*(?:probation|إنذار|إنذار أكاديمي)",
        "answer_template": "يتم وضع الطالب تحت الإنذار الأكاديمي إذا انخفض معدله التراكمي عن 2.0. يجب على الطالب رفع معدله إلى 2.0 أو أعلى خلال فصلين دراسيين متتاليين، وإلا سيتم فصله من الكلية.",
        "category": "regulations",
        "priority": 1,
        "metadata": {"applies_to": "all_students"}
    },
    {
        "question_pattern": r"(?:how|كيف).*(?:appeal|استئناف|الاستئناف).*(?:grade|درجة)",
        "answer_template": "يمكنك استئناف درجة خلال أسبوعين من إعلان النتائج. يجب تقديم طلب خطي إلى رئيس القسم مع توضيح أسباب الاستئناف. يتم تشكيل لجنة لمراجعة الطلب.",
        "category": "regulations",
        "priority": 2,
        "metadata": {"applies_to": "all_students"}
    },
    {
        "question_pattern": r"(?:what|ما).*(?:tuition|رسوم|الرسوم|fees|الرسوم الدراسية)",
        "answer_template": "الرسوم الدراسية تختلف حسب التخصص وعدد الساعات المسجلة. يرجى التواصل مع مكتب شؤون الطلاب أو زيارة موقع الجامعة للحصول على معلومات دقيقة عن الرسوم.",
        "category": "fees",
        "priority": 1,
        "metadata": {"applies_to": "all_students"}
    },
    {
        "question_pattern": r"(?:when|متى).*(?:payment|دفع|الدفع|pay|الدفع).*(?:due|مستحقة)",
        "answer_template": "يجب دفع الرسوم الدراسية قبل بداية كل فصل دراسي. عادة ما يكون الموعد النهائي للدفع قبل أسبوع من بداية الفصل. يمكنك الدفع عبر البنك أو عبر النظام الإلكتروني.",
        "category": "fees",
        "priority": 1,
        "metadata": {"applies_to": "all_students"}
    },
    {
        "question_pattern": r"(?:what|ما).*(?:scholarship|منحة|المنحة|scholarships|المنح)",
        "answer_template": "تقدم الجامعة منح دراسية للطلاب المتفوقين والطلاب ذوي الحاجة المالية. يمكنك التقديم على المنح من خلال مكتب شؤون الطلاب. تتطلب المنح عادة معدل تراكمي لا يقل عن 3.5.",
        "category": "fees",
        "priority": 2,
        "metadata": {"applies_to": "all_students"}
    },
    {
        "question_pattern": r"(?:how|كيف).*(?:transfer|نقل|النقل).*(?:course|مقرر|credits|ساعات)",
        "answer_template": "يمكن نقل الساعات المعتمدة من جامعات أخرى معتمدة بموافقة العميد. يجب أن تكون الدرجة C أو أعلى، وأن يكون المقرر متطابقاً مع المقرر المطلوب. الحد الأقصى للساعات المنقولة هو 60 ساعة.",
        "category": "regulations",
        "priority": 2,
        "metadata": {"applies_to": "all_students"}
    },
    {
        "question_pattern": r"(?:what|ما).*(?:incomplete|ناقص|ناقصة).*(?:grade|درجة)",
        "answer_template": "الدرجة 'I' (Incomplete) تُمنح عندما لا يتمكن الطالب من إكمال متطلبات المقرر بسبب ظروف قاهرة. يجب إكمال المتطلبات خلال الفصل التالي، وإلا تتحول الدرجة إلى F.",
        "category": "regulations",
        "priority": 2,
        "metadata": {"applies_to": "all_students"}
    },
    {
        "question_pattern": r"(?:when|متى).*(?:summer|صيفي|الصيفي).*(?:semester|فصل)",
        "answer_template": "الفصل الصيفي يبدأ عادة في شهر يونيو/حزيران ويمتد لمدة 8-10 أسابيع. التسجيل في الفصل الصيفي اختياري. يمكنك التسجيل في ما يصل إلى 9 ساعات معتمدة في الفصل الصيفي.",
        "category": "deadlines",
        "priority": 2,
        "metadata": {"applies_to": "all_students"}
    },
    {
        "question_pattern": r"(?:what|ما).*(?:attendance|حضور|الحضور).*(?:policy|سياسة|قواعد)",
        "answer_template": "يجب على الطلاب حضور ما لا يقل عن 75% من المحاضرات. الطلاب الذين تقل نسبة حضورهم عن 75% قد يُمنعون من دخول الامتحان النهائي. بعض المقررات قد تتطلب نسبة حضور أعلى.",
        "category": "regulations",
        "priority": 1,
        "metadata": {"applies_to": "all_students"}
    },
    {
        "question_pattern": r"(?:how|كيف).*(?:request|طلب|الطلب).*(?:transcript|كشف|كشف الدرجات)",
        "answer_template": "يمكنك طلب كشف الدرجات من خلال مكتب التسجيل. يجب تقديم طلب خطي مع دفع الرسوم المطلوبة. عادة ما يستغرق إصدار كشف الدرجات 3-5 أيام عمل.",
        "category": "regulations",
        "priority": 2,
        "metadata": {"applies_to": "all_students"}
    },
    {
        "question_pattern": r"(?:what|ما).*(?:honor|شرف|شرفي).*(?:roll|قائمة|dean|عميد)",
        "answer_template": "قائمة العميد للشرف تشمل الطلاب الذين حصلوا على معدل تراكمي 3.5 أو أعلى في الفصل الدراسي. يتم الإعلان عن القائمة في نهاية كل فصل دراسي.",
        "category": "regulations",
        "priority": 2,
        "metadata": {"applies_to": "all_students"}
    },
]


async def seed_faq_entries():
    """
    Seed FAQ entries into database
    
    بذر إدخالات الأسئلة الشائعة في قاعدة البيانات
    """
    # Initialize database
    await init_db()
    
    async with AsyncSessionLocal() as session:
        try:
            # Check if FAQs already exist
            from sqlalchemy import select
            result = await session.execute(select(FAQEntry))
            existing_faqs = result.scalars().all()
            
            if existing_faqs:
                print(f"⚠️ Found {len(existing_faqs)} existing FAQ entries. Skipping seed.")
                return
            
            # Create FAQ entries
            created_count = 0
            for faq_data in FAQ_DATA:
                faq_entry = FAQEntry(
                    question_pattern=faq_data["question_pattern"],
                    answer_template=faq_data["answer_template"],
                    category=faq_data["category"],
                    priority=faq_data.get("priority", 1),
                    metadata=faq_data.get("metadata", {}),
                    is_active=True
                )
                session.add(faq_entry)
                created_count += 1
            
            await session.commit()
            print(f"✅ Successfully seeded {created_count} FAQ entries!")
            
        except Exception as e:
            await session.rollback()
            print(f"❌ Error seeding FAQ entries: {e}")
            raise


if __name__ == "__main__":
    print("🌱 Starting FAQ seed script...")
    asyncio.run(seed_faq_entries())
    print("✅ FAQ seed script completed!")
