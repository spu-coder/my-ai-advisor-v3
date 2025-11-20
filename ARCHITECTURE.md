# System Architecture / هندسة النظام

> **Elite CTO Mode** - Production-ready microservices architecture with async PostgreSQL, decoupled services, and comprehensive security.

> **وضع CTO المتقدم** - هندسة microservices جاهزة للإنتاج مع PostgreSQL غير المتزامن وخدمات منفصلة وأمان شامل.

---

## 📊 System Overview / نظرة عامة على النظام

```mermaid
graph TD
    A[Frontend<br/>Streamlit] -->|HTTP/HTTPS| B[API Gateway<br/>FastAPI]
    B -->|JWT Auth| C[Security Layer<br/>Middleware Stack]
    C -->|Async Session| D[(PostgreSQL<br/>Async SQLAlchemy 2.0)]
    C -->|HTTP| E[LLM Service<br/>Decoupled]
    E -->|Interface| F[Documents Service<br/>ChromaDB]
    E -->|Interface| G[Progress Service<br/>PostgreSQL]
    E -->|Interface| H[Graph Service<br/>Neo4j]
    B -->|HTTP| I[Ollama Service<br/>Local LLM]
    B -->|HTTP| J[Redis<br/>Cache & Rate Limiting]
    F -->|Vector Store| K[(ChromaDB<br/>Vector Database)]
    H -->|Graph DB| L[(Neo4j<br/>Graph Database)]
    
    style D fill:#336791,color:#fff
    style K fill:#FF6B6B,color:#fff
    style L fill:#008CC1,color:#fff
    style E fill:#10B981,color:#fff
    style C fill:#F59E0B,color:#fff
```

---

## 🔐 Authentication Flow / تدفق المصادقة

```mermaid
sequenceDiagram
    participant U as User / المستخدم
    participant F as Frontend
    participant G as API Gateway
    participant RL as RateLimit Middleware
    participant SH as SecurityHeaders Middleware
    participant JWT as JWT Auth Middleware
    participant IV as InputValidation Middleware
    participant DB as PostgreSQL
    
    U->>F: Login Request / طلب تسجيل الدخول
    F->>G: POST /token/json
    G->>RL: 1. Rate Limit Check / فحص معدل الطلبات
    RL->>SH: 2. Security Headers / رؤوس الأمان
    SH->>IV: 3. Input Validation / التحقق من المدخلات
    IV->>JWT: 4. JWT Processing / معالجة JWT
    JWT->>DB: 5. User Authentication / مصادقة المستخدم
    DB-->>JWT: User Data / بيانات المستخدم
    JWT-->>IV: JWT Token / رمز JWT
    IV-->>SH: Validated Request / طلب محقق
    SH-->>RL: Secure Response / استجابة آمنة
    RL-->>G: Rate Limited Response / استجابة محدودة المعدل
    G-->>F: Access Token / رمز الوصول
    F-->>U: Authenticated / مصادق عليه
```

---

## 🏗️ Service Architecture / هندسة الخدمات

### Core Services / الخدمات الأساسية

#### 1. API Gateway (FastAPI)
- **Role / الدور**: Entry point, routing, authentication
- **Technology / التقنية**: FastAPI, Async Python
- **Database / قاعدة البيانات**: PostgreSQL (async)

#### 2. LLM Service (Decoupled)
- **Role / الدور**: Intent detection, response generation
- **Technology / التقنية**: OpenAI API / Ollama
- **Decoupling / الفصل**: Uses ServiceAdapter interface, no direct DB access

#### 3. Documents Service
- **Role / الدور**: Document ingestion, RAG retrieval
- **Technology / التقنية**: ChromaDB, LangChain
- **Storage / التخزين**: Vector embeddings in ChromaDB

#### 4. Progress Service
- **Role / الدور**: Student academic progress tracking
- **Technology / التقنية**: PostgreSQL, SQLAlchemy 2.0 (async)
- **Storage / التخزين**: Student records, grades, GPA calculations

#### 5. Graph Service
- **Role / الدور**: Course relationships, skills mapping
- **Technology / التقنية**: Neo4j
- **Storage / التخزين**: Graph database for course prerequisites

---

## 🔒 Security Architecture / هندسة الأمان

### Middleware Stack Order / ترتيب طبقات Middleware

```
Request Flow / تدفق الطلب:
1. RateLimitMiddleware      → Prevents DDoS / منع DDoS
2. RequestSizeMiddleware    → Limits payload size / تحديد حجم البيانات
3. WAFMiddleware            → Web Application Firewall / جدار حماية التطبيق
4. InputSanitizationMiddleware → Sanitizes inputs / تنظيف المدخلات
5. JWTAuthMiddleware        → JWT authentication / مصادقة JWT
6. SecurityHeadersMiddleware → Security headers / رؤوس الأمان
7. AuditLoggingMiddleware   → Request logging / تسجيل الطلبات
8. CORSMiddleware           → CORS handling / معالجة CORS
```

### Database Security / أمان قاعدة البيانات

- ✅ **Async PostgreSQL** - Production-ready database
- ✅ **SQLite Forbidden** - Strictly prohibited
- ✅ **Connection Pooling** - Efficient resource management
- ✅ **Prepared Statements** - SQL injection prevention

---

## 📦 Data Flow / تدفق البيانات

### RAG Query Flow / تدفق استعلام RAG

```mermaid
sequenceDiagram
    participant U as User
    participant G as API Gateway
    participant L as LLM Service
    participant D as Documents Service
    participant C as ChromaDB
    participant O as Ollama/OpenAI
    
    U->>G: Chat Question / سؤال الدردشة
    G->>L: process_agentic_query()
    L->>L: Determine Intent / تحديد النية
    L->>D: retrieve_context()
    D->>C: Vector Search / بحث المتجهات
    C-->>D: Relevant Context / السياق ذو الصلة
    D-->>L: Context String / نص السياق
    L->>O: Generate Response / توليد الاستجابة
    O-->>L: LLM Response / استجابة LLM
    L-->>G: Formatted Answer / إجابة منسقة
    G-->>U: Final Response / الاستجابة النهائية
```

---

## 🗄️ Database Schema / مخطط قاعدة البيانات

### PostgreSQL Tables / جداول PostgreSQL

```sql
-- Users Table / جدول المستخدمين
users (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR UNIQUE,
    full_name VARCHAR,
    hashed_password VARCHAR,
    role VARCHAR DEFAULT 'student',
    email VARCHAR UNIQUE,
    university_password VARCHAR,
    created_at TIMESTAMP,
    last_data_sync TIMESTAMP
)

-- Progress Records / سجلات التقدم
progress_records (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR REFERENCES users(user_id),
    course_code VARCHAR,
    grade VARCHAR,
    hours INTEGER,
    semester VARCHAR,
    course_name VARCHAR,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
)

-- Chat Messages / رسائل الدردشة
chat_messages (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR REFERENCES users(user_id),
    role VARCHAR,
    content TEXT,
    intent VARCHAR,
    created_at TIMESTAMP
)

-- Notifications / الإشعارات
notifications (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR REFERENCES users(user_id),
    message VARCHAR,
    type VARCHAR,
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP
)
```

---

## 🚀 Deployment Architecture / هندسة النشر

### Docker Compose Services / خدمات Docker Compose

```yaml
Services:
  - frontend (Streamlit)
  - backend (FastAPI API Gateway)
  - postgres (PostgreSQL 15)
  - redis (Cache & Rate Limiting)
  - llm-service (Ollama)
  - vector-db (ChromaDB)
  - graph-db (Neo4j)
```

### Environment Variables / متغيرات البيئة

- `DATABASE_URL`: PostgreSQL connection (asyncpg)
- `SECRET_KEY`: JWT signing key
- `LLM_PROVIDER`: openai | ollama
- `REDIS_CACHE_URL`: Redis connection
- `NEO4J_PASSWORD`: Neo4j authentication

---

## 📝 Key Design Decisions / قرارات التصميم الرئيسية

1. **Async PostgreSQL** - All database operations are async for better performance
2. **Service Decoupling** - LLM service uses interfaces, not direct DB access
3. **Middleware Order** - Strict security middleware pipeline
4. **Type Safety** - Strict typing with minimal `Any` usage
5. **Bilingual Support** - All documentation in English and Arabic

---

## 🔄 Future Enhancements / التحسينات المستقبلية

- [ ] GraphQL API layer
- [ ] WebSocket support for real-time chat
- [ ] Advanced caching strategies
- [ ] Multi-tenant support
- [ ] Advanced analytics dashboard

---

**Last Updated / آخر تحديث**: 2025-01-27
**Version / الإصدار**: 2.0.0
**Status / الحالة**: Production Ready / جاهز للإنتاج ✅

