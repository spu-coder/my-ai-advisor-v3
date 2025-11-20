# المرشد الأكاديمي الذكي (Smart Academic Advisor)
# Smart Academic Advisor System

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.28+-red.svg)](https://streamlit.io/)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)](https://www.docker.com/)

## 📋 نظرة عامة / Overview

هذا المشروع هو تطبيق متكامل لنظام مرشد أكاديمي ذكي يعتمد على بنية الخدمات المصغرة (Microservices) وتقنية Agentic RAG، ويهدف إلى مساعدة الطلاب في استفساراتهم الأكاديمية وتتبع تقدمهم.

This project is a comprehensive smart academic advisor system based on microservices architecture and Agentic RAG technology, designed to help students with their academic inquiries and track their progress.

---

## ✨ الميزات الرئيسية / Key Features

### 🏗️ البنية المعمارية / Architecture
- **بنية الخدمات المصغرة (Microservices):** فصل منطق العمل إلى خدمات واضحة (المستخدمون، التقدم، المستندات، الإشعارات، الرسم البياني، LLM)
- **API Gateway:** نقطة دخول موحدة لجميع الطلبات مع التحقق من الأمان والتوجيه
- **Agentic RAG:** استخدام وكيل ذكي لتحديد نية المستخدم وتوجيه السؤال إلى الأداة المناسبة

### 🔒 الأمان / Security
- **مصادقة JWT (JWT Authentication):** حماية جميع المسارات باستخدام رموز JWT
- **تفويض قائم على الأدوار (Role-Based Authorization):** فصل الصلاحيات بين الطلاب والإداريين
- **OWASP Security Best Practices:** تطبيق أفضل ممارسات أمان OWASP:
  - Rate limiting في الطبقة الأولى ثم مصادقة JWT لتجنب استنزاف الموارد
  - Web Application Firewall (WAF) مدمج مع كشف الروبوتات ورصد أنماط الحقن
  - Input sanitization ذكي بعد التحقق من الهوية لضمان الأداء
  - Security headers (XSS, CSRF protection)
  - Request size limiting
  - Audit logging شامل مع تتبع الزمن، العنوان، والنتيجة
  - SQL injection prevention

### ☁️ LLM Strategy & Caching
- **مزودات متعددة (OpenAI أو Ollama):** اختيار المزود عبر `LLM_PROVIDER` مع آلية سقوط تلقائي للنسخة المحلية
- **Redis-backed caching:** تخزين إجابات LLM وسياقات RAG لتقليل زمن الاستجابة وتكاليف التشغيل
- **Intent fallback routing:** يوجّه الطلبات إلى `query_rag` تلقائياً عند انخفاض الثقة بالتصنيف

### 🗄️ طبقة البيانات / Data Layer
- **PostgreSQL افتراضي للإنتاج:** `DATABASE_URL` يوجّه إلى PostgreSQL مع جلسة موحدة للخدمات
- **تملك الخدمة للبيانات:** كل خدمة تتعامل مع الجداول الخاصة بها عبر طبقة الوصول الخاصة بها
- **Redis كطبقة تخزين مؤقت:** مشاركة بين تحديد المعدل، التخزين المؤقت لـ RAG، ومسارات LLM

### 📄 معالجة البيانات / Data Processing
- **معالجة متعددة الوسائط (Multimodal Processing):** دعم فهرسة المستندات من أنواع مختلفة:
  - PDF (مع دعم OCR للصور المضمنة)
  - DOCX, DOC
  - صور (JPG, PNG, TIFF) مع OCR
  - ملفات نصية (TXT)
- **RAG (Retrieval Augmented Generation):** فهرسة ذكية للمستندات مع ChromaDB
- **Graph Database:** تخزين العلاقات بين المقررات والمهارات في Neo4j

### ⚙️ التكوين والإعدادات / Configuration
- **Vibe Config:** إدارة الإعدادات الرئيسية عبر ملف `config/settings.json` مركزي
- **Dynamic Configuration:** تغيير إعدادات النظام دون إعادة التشغيل
- **Environment Variables:** دعم متغيرات البيئة للتكوين المرن

### 📊 الميزات الوظيفية / Functional Features
- **دردشة ذكية (Smart Chat):** Agentic RAG للرد على الأسئلة الأكاديمية
- **تحليل التقدم (Progress Analysis):** تحليل السجل الأكاديمي وتحديد المقررات القابلة للتسجيل
- **محاكي المعدل (GPA Simulator):** توقع المعدل التراكمي بناءً على الدرجات المتوقعة
- **الرسم البياني للمهارات (Skills Graph):** استكشاف المهارات المكتسبة من المقررات
- **الإشعارات (Notifications):** تنبيهات ذكية للطلاب حول تقدمهم الأكاديمي
- **مزامنة البيانات (Data Sync):** جمع البيانات من النظام الجامعي تلقائياً

### 🐳 Docker Support
- **Docker Compose:** تشغيل جميع الخدمات بملف واحد
- **Containerization:** جميع الخدمات معزولة في حاويات منفصلة
- **Volume Management:** إدارة البيانات المستمرة بشكل آمن

---

## 📦 متطلبات التشغيل / Requirements

### المتطلبات الأساسية / Basic Requirements
- **Docker** و **Docker Compose** (الإصدار 3.8 أو أحدث)
- **8 GB RAM** على الأقل (للنماذج اللغوية)
- **10 GB** مساحة تخزين مجانية
- لا حاجة لتثبيت PostgreSQL أو Redis يدوياً؛ يتم تشغيلهما تلقائياً عبر Docker

### المتطلبات الاختيارية / Optional Requirements
- **GPU** (لتحسين أداء النماذج اللغوية - اختياري)
- **Neo4j Desktop** (لإدارة قاعدة بيانات الرسم البياني محلياً - اختياري)

---

## 🚀 خطوات التشغيل / Installation Steps

### 1. فك ضغط المشروع / Extract Project
```bash
# قم بفك ضغط الملف الذي تم تسليمه إليك
# Extract the project files
```

### 2. إنشاء المجلدات اللازمة / Create Required Directories
انتقل إلى المجلد الرئيسي للمشروع (حيث يوجد ملف `docker-compose.yml`) وقم بتنفيذ الأمر التالي:

Navigate to the project root directory (where `docker-compose.yml` exists) and run:

```bash
# Windows (PowerShell)
mkdir -p data, config, logs

# Linux/Mac
mkdir -p data config logs
```

**ملاحظة:** المجلدات التالية مهمة:
- `data/`: لوضع ملفات المستندات (PDF, DOCX, صور) التي تريد فهرستها
- `config/`: يحتوي على `settings.json` لإعدادات التكوين
- `logs/`: لتخزين ملفات التسجيل

**Note:** The following directories are important:
- `data/`: For document files (PDF, DOCX, images) to be indexed
- `config/`: Contains `settings.json` for configuration
- `logs/`: For storing log files

### 3. تحقق من ملف التكوين / Verify Configuration File
تأكد من وجود ملف `config/settings.json` وتعديله حسب الحاجة:

Ensure `config/settings.json` exists and modify as needed:

```json
{
    "llm_model": "llama3:8b",
    "rag_top_k": 5,
    "gpa_scale": {
        "A+": 4.0,
        "A": 4.0,
        "A-": 3.7,
        "B+": 3.3,
        "B": 3.0,
        "B-": 2.7,
        "C+": 2.3,
        "C": 2.0,
        "C-": 1.7,
        "D+": 1.3,
        "D": 1.0,
        "F": 0.0
    },
    "security": {
        "access_token_expire_minutes": 30,
        "admin_emails": ["admin@example.com"]
    },
    "notifications": {
        "gpa_warning_threshold": 2.0,
        "low_gpa_message": "تنبيه: معدلك التراكمي أقل من الحد الأدنى"
    }
}
```

### 4. إعداد متغيرات البيئة / Configure Environment Variables

1. انسخ الملف `env.example` وأعد تسميته إلى `.env` في جذر المشروع.
2. حدّث القيم التالية قبل تشغيل Docker:
   - `SECRET_KEY`: مفتاح عشوائي طويل لتوقيع رموز JWT.
   - `NEO4J_PASSWORD`: كلمة مرور قاعدة بيانات Neo4j.
   - `OLLAMA_MODEL`: اسم النموذج المطلوب تحميله عبر خدمة Ollama (الافتراضي `llama3:8b`).
   - `VERIFY_UNIVERSITY_SSL`: اجعله `false` فقط في بيئات التطوير عندما لا يتوفر证 SSL صحيح.
   - `DATABASE_URL` أو متغيرات PostgreSQL (`POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`) لضبط قاعدة البيانات المركزية.
    - `RATE_LIMIT_REDIS_URL`: مسار Redis لتخزين حالة تحديد المعدل (الافتراضي يشير إلى خدمة Redis في Docker).

> ⚠️ لا تحفظ ملف `.env` في أنظمة التحكم بالنسخ، وقد تمت إضافة الملف إلى `.gitignore` بالفعل.

### 5. إضافة المستندات (اختياري) / Add Documents (Optional)
ضع المستندات التي تريد فهرستها في مجلد `data/`:

Place documents to be indexed in the `data/` folder:

```
data/
├── اللائحة_الداخلية.pdf
├── توصيف_المقررات.docx
├── الخطة_الدراسية.pdf
└── ...
```

### 6. تشغيل النظام / Start the System

#### الطريقة الأولى: Docker Compose (موصى بها) / Method 1: Docker Compose (Recommended)
```bash
# بناء وتشغيل جميع الخدمات
# Build and run all services
docker-compose up --build -d

# عرض حالة الخدمات
# View service status
docker-compose ps

# عرض السجلات
# View logs
docker-compose logs -f
```

**ملاحظة:** قد يستغرق هذا الأمر بعض الوقت في المرة الأولى لتنزيل الصور وبناء الحاويات.

**Note:** This may take some time on first run to download images and build containers.

> ℹ️ خدمة `llm-service` تقوم الآن بتحميل النموذج المحدد تلقائياً في حال عدم توفره داخل الحجم الدائم `ollama_data`.
>
> ℹ️ سيتم تشغيل خدمات PostgreSQL و Redis تلقائياً لتوفير قاعدة بيانات مركزية وتحديد معدل موزّع.

#### الطريقة الثانية: تشغيل يدوي / Method 2: Manual Setup
راجع ملف `DESIGN_METHODOLOGY.md` للتعليمات التفصيلية.

See `DESIGN_METHODOLOGY.md` for detailed instructions.

### 7. الوصول إلى التطبيق / Access the Application

بعد تشغيل النظام، افتح متصفحك على العنوان:

After starting the system, open your browser at:

- **الواجهة الأمامية (Frontend):** http://localhost:8501
- **API Documentation (Swagger):** http://localhost:8000/docs
- **Neo4j Browser:** http://localhost:7474
- **ChromaDB:** http://localhost:8001

---

## 🎯 الإعداد الأولي داخل التطبيق / Initial Setup in Application

بعد فتح التطبيق، اتبع الخطوات التالية:

After opening the application, follow these steps:

### 1. تسجيل الدخول/التسجيل / Login/Registration

#### إنشاء حساب Admin / Create Admin Account
1. من تبويب "تسجيل أدمن"، قم بإنشاء حساب admin أولاً
   - البريد: `admin@example.com`
   - كلمة المرور: `password123` (أو أي كلمة مرور قوية)
   - المعرف: `admin_001`

2. سجل الدخول باستخدام حساب **admin**

#### إنشاء حساب طالب / Create Student Account
1. من تبويب "تسجيل طالب جديد"، قم بإنشاء حساب طالب
   - الرقم الجامعي: رقمك الجامعي الفعلي
   - كلمة المرور: كلمة سر نظام الليرناتا
   - سيتم التحقق من البيانات تلقائياً من النظام الجامعي

### 2. تنفيذ الإعداد الأولي (من الشريط الجانبي) / Execute Initial Setup (from Sidebar)

**ملاحظة:** يجب أن تكون مسجلاً كـ admin لتنفيذ هذه الخطوات.

**Note:** You must be logged in as admin to execute these steps.

#### أ. إنشاء مستخدم تجريبي (طالب) / Create Demo User (Student)
- اضغط على زر "إنشاء مستخدم تجريبي" في الشريط الجانبي
- سيتم إنشاء مستخدم طالب تجريبي (`test@example.com`) مع سجل درجات أولي

#### ب. فهرسة الرسم البياني (Neo4j) / Index Graph Data (Neo4j)
- اضغط على زر "🌳 فهرسة الرسم البياني (Neo4j)"
- ستقوم هذه الخطوة بإدخال بيانات المهارات والمقررات في Neo4j
- قد تستغرق بضع ثوانٍ

#### ج. فهرسة المستندات (RAG) / Index Documents (RAG)
- اضغط على زر "📄 فهرسة المستندات (RAG)"
- ستقوم هذه الخطوة بمعالجة جميع الملفات في مجلد `data` (بما في ذلك OCR للصور) وفهرستها في ChromaDB
- **ملاحظة:** قد تستغرق هذه العملية عدة دقائق حسب عدد وحجم الملفات

**⚠️ تحذير:** تأكد من وجود مستندات في مجلد `data/` قبل تنفيذ هذه الخطوة.

**⚠️ Warning:** Ensure documents exist in `data/` folder before executing this step.

### 3. استخدام النظام / Using the System

بعد إكمال الإعداد الأولي، يمكنك:

After completing initial setup, you can:

- ✅ استخدام واجهة الدردشة الذكية
- ✅ تحليل التقدم الأكاديمي
- ✅ محاكاة المعدل التراكمي
- ✅ استكشاف المهارات من المقررات
- ✅ استقبال الإشعارات والتنبيهات

---

## 🧪 الاختبار / Testing

### اختبار الواجهة الخلفية / Backend Testing

#### 1. اختبار Health Check
```bash
curl http://localhost:8000/health
```

يجب أن يعيد: `{"status": "ok", "service": "API Gateway"}`

#### 2. اختبار تسجيل الدخول
```bash
curl -X POST "http://localhost:8000/token/json" \
  -H "Content-Type: application/json" \
  -d '{
    "identifier": "admin@example.com",
    "password": "password123"
  }'
```

#### 3. اختبار الدردشة (يتطلب token)
```bash
TOKEN="your_jwt_token_here"
curl -X POST "http://localhost:8000/chat" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "ما هي متطلبات التخرج؟",
    "user_id": "admin_001"
  }'
```

### اختبار الواجهة الأمامية / Frontend Testing

1. افتح http://localhost:8501
2. سجل الدخول
3. جرب جميع الميزات:
   - الدردشة الذكية
   - تحليل التقدم
   - محاكي المعدل
   - الرسم البياني للمهارات

### اختبار الأمان / Security Testing

#### Rate Limiting Test
```bash
# محاولة إرسال 100+ طلب في دقيقة واحدة
for i in {1..150}; do
  curl http://localhost:8000/health
done
```

يجب أن تحصل على `429 Too Many Requests` بعد 100 طلب.

#### Authentication Test
```bash
# محاولة الوصول إلى مسار محمي بدون token
curl http://localhost:8000/chat
```

يجب أن تحصل على `401 Unauthorized`.

---

## 🔧 التكوين المتقدم / Advanced Configuration

### تغيير نموذج LLM / Change LLM Model

في ملف `config/settings.json`:

In `config/settings.json`:

```json
{
    "llm_model": "llama3:8b"  // يمكن تغييره إلى "llama3:70b" أو أي نموذج آخر
}
```

**ملاحظة:** يجب أن يكون النموذج محملاً في Ollama أولاً.

**Note:** The model must be loaded in Ollama first.

### تحميل نموذج LLM في Ollama / Load LLM Model in Ollama

```bash
# الدخول إلى حاوية Ollama
docker exec -it my-ai-advisor-llm-service-1 bash

# تحميل النموذج
ollama pull llama3:8b

# أو تحميل نموذج أكبر
ollama pull llama3:70b
```

### تغيير إعدادات الأمان / Change Security Settings

في ملف `config/settings.json`:

In `config/settings.json`:

```json
{
    "security": {
        "access_token_expire_minutes": 60,  // تغيير مدة انتهاء صلاحية Token
        "admin_emails": ["admin@example.com", "another@example.com"]
    }
}
```

### إعدادات قاعدة البيانات / Database Settings

في ملف `docker-compose.yml`:

In `docker-compose.yml`:

```yaml
environment:
  - NEO4J_PASSWORD=${NEO4J_PASSWORD:?must be set}  # اضبط كلمة مرور Neo4j من .env
  - SECRET_KEY=${SECRET_KEY:?must be set}          # اضبط مفتاح JWT من .env
```

**⚠️ تحذير:** لا تستخدم هذه القيم الافتراضية في الإنتاج!

**⚠️ Warning:** Do not use these default values in production!

---

## 🐛 استكشاف الأخطاء وإصلاحها / Troubleshooting

### المشكلة: الخدمات لا تبدأ / Services Won't Start

**الحل:**
```bash
# التحقق من حالة الخدمات
docker-compose ps

# عرض السجلات
docker-compose logs backend
docker-compose logs frontend

# إعادة بناء الحاويات
docker-compose down
docker-compose up --build -d
```

### المشكلة: Ollama لا يستجيب / Ollama Not Responding

**الحل:**
```bash
# التحقق من حالة Ollama
docker-compose logs llm-service

# إعادة تشغيل خدمة Ollama
docker-compose restart llm-service

# تحميل النموذج يدوياً
docker exec -it my-ai-advisor-llm-service-1 ollama pull llama3:8b
```

### المشكلة: ChromaDB لا يتصل / ChromaDB Connection Failed

**الحل:**
```bash
# التحقق من حالة ChromaDB
docker-compose logs vector-db

# إعادة تشغيل ChromaDB
docker-compose restart vector-db

# التحقق من الاتصال
curl http://localhost:8001/api/v1/heartbeat
```

### المشكلة: Neo4j لا يتصل / Neo4j Connection Failed

**الحل:**
```bash
# التحقق من حالة Neo4j
docker-compose logs graph-db

# إعادة تشغيل Neo4j
docker-compose restart graph-db

# فتح Neo4j Browser
# افتح http://localhost:7474
# استخدم بيانات الدخول المعرفة في متغيرات البيئة (.env)
```

### المشكلة: فشل فهرسة المستندات / Document Indexing Failed

**الحل:**
1. تأكد من وجود ملفات في مجلد `data/`
2. تحقق من صيغة الملفات (PDF, DOCX, TXT مدعومة)
3. تحقق من السجلات:
   ```bash
   docker-compose logs backend | grep DOCUMENTS_SERVICE
   ```

### المشكلة: خطأ في المصادقة / Authentication Error

**الحل:**
1. تحقق من أن SECRET_KEY في `docker-compose.yml` صحيح
2. تحقق من أن Token لم ينتهِ صلاحيته
3. أعد تسجيل الدخول

---

## 📚 الوثائق الإضافية / Additional Documentation

- **DESIGN_METHODOLOGY.md:** شرح شامل للمنهجية التصميمية والبنية المعمارية
- **API Documentation:** http://localhost:8000/docs (Swagger UI)
- **Code Documentation:** جميع الملفات تحتوي على docstrings بالعربية والإنجليزية

---

## 🔐 الأمان في الإنتاج / Production Security

**⚠️ مهم جداً:** قبل نشر النظام في الإنتاج، تأكد من:

**⚠️ Very Important:** Before deploying to production, ensure:

1. ✅ تغيير جميع كلمات المرور الافتراضية
2. ✅ تغيير SECRET_KEY في `docker-compose.yml`
3. ✅ تعطيل CORS للوصول من أي مكان (`*`)
4. ✅ تفعيل HTTPS
5. ✅ استخدام قاعدة بيانات آمنة (PostgreSQL بدلاً من SQLite)
6. ✅ تفعيل Rate Limiting بشكل أكثر صرامة
7. ✅ إعداد نسخ احتياطية منتظمة
8. ✅ مراقبة السجلات بانتظام

---

## 📝 الترخيص / License

هذا المشروع مطور لأغراض أكاديمية.

This project is developed for academic purposes.

---

## 👥 المساهمون / Contributors

- فريق التطوير / Development Team

---

## 📞 الدعم / Support

للأسئلة والدعم، يرجى فتح issue في المستودع.

For questions and support, please open an issue in the repository.

---

**تم التطوير بواسطة:** فريق المرشد الأكاديمي الذكي  
**Developed by:** Smart Academic Advisor Team

**آخر تحديث / Last Updated:** 2025
