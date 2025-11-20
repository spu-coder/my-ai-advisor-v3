# دليل الاختبار / Testing Guide

## نظرة عامة / Overview

هذا الدليل يشرح كيفية اختبار نظام المرشد الأكاديمي الذكي بشكل شامل.

This guide explains how to comprehensively test the Smart Academic Advisor system.

---

## أنواع الاختبارات / Types of Tests

### 1. اختبارات الوحدة (Unit Tests)
اختبار كل وظيفة بشكل منفصل.

Test each function independently.

### 2. اختبارات التكامل (Integration Tests)
اختبار تكامل الخدمات معاً.

Test services integration together.

### 3. اختبارات النهاية إلى النهاية (E2E Tests)
اختبار السيناريوهات الكاملة من البداية للنهاية.

Test complete scenarios from start to end.

### 4. اختبارات الأمان (Security Tests)
اختبار إجراءات الأمان والحماية.

Test security measures and protection.

---

## اختبارات الواجهة الخلفية / Backend Tests

### 1. اختبار Health Check

```bash
# Test health endpoint
curl http://localhost:8000/health

# Expected response:
# {"status": "ok", "service": "API Gateway"}
```

### 2. اختبار المصادقة / Authentication Tests

#### تسجيل Admin جديد
```bash
curl -X POST "http://localhost:8000/register/admin" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN" \
  -d '{
    "user_id": "admin_test",
    "full_name": "Test Admin",
    "email": "test@example.com",
    "password": "test123456"
  }'
```

#### تسجيل الدخول
```bash
curl -X POST "http://localhost:8000/token/json" \
  -H "Content-Type: application/json" \
  -d '{
    "identifier": "admin@example.com",
    "password": "password123"
  }'
```

**Expected:** JWT token in response

### 3. اختبار الدردشة / Chat Tests

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

**Expected:** Answer with source and intent

### 4. اختبار Rate Limiting

```bash
# Send 150 requests rapidly
for i in {1..150}; do
  curl http://localhost:8000/health &
done

# Expected: After 100 requests, should get 429 Too Many Requests
```

### 5. اختبار Authorization

```bash
# Try to access protected endpoint without token
curl http://localhost:8000/chat

# Expected: 401 Unauthorized
```

---

## اختبارات الواجهة الأمامية / Frontend Tests

### 1. اختبار تسجيل الدخول
1. افتح http://localhost:8501
2. جرب تسجيل الدخول بحساب admin
3. تحقق من نجاح تسجيل الدخول

### 2. اختبار الدردشة الذكية
1. سجل الدخول
2. اذهب إلى "الدردشة الذكية"
3. اسأل: "ما هي متطلبات التخرج؟"
4. تحقق من الحصول على إجابة

### 3. اختبار تحليل التقدم
1. سجل الدخول كطالب
2. اذهب إلى "تحليل التقدم"
3. اضغط "تحليل سجلي الأكاديمي"
4. تحقق من عرض النتائج

### 4. اختبار محاكي المعدل
1. اذهب إلى "محاكي المعدل"
2. أدخل بياناتك الحالية
3. أدخل المقررات المتوقعة
4. اضغط "حساب المعدل المتوقع"
5. تحقق من النتيجة

---

## اختبارات الأمان / Security Tests

### 1. اختبار Input Validation

```bash
# Test SQL injection attempt
curl -X POST "http://localhost:8000/chat" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "'; DROP TABLE users; --",
    "user_id": "admin_001"
  }'

# Expected: Should be sanitized, not cause SQL injection
```

### 2. اختبار XSS Protection

```bash
# Test XSS attempt
curl -X POST "http://localhost:8000/chat" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "<script>alert(\"XSS\")</script>",
    "user_id": "admin_001"
  }'

# Expected: Should be sanitized
```

### 3. اختبار Authorization Bypass

```bash
# Try to access another user's data
curl -X GET "http://localhost:8000/progress/analyze/another_user_id" \
  -H "Authorization: Bearer $TOKEN"

# Expected: 403 Forbidden
```

---

## اختبارات الأداء / Performance Tests

### 1. اختبار وقت الاستجابة

```bash
# Measure response time
time curl -X POST "http://localhost:8000/chat" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "ما هو المعدل التراكمي؟",
    "user_id": "admin_001"
  }'
```

**Expected:** < 5 seconds for RAG queries

### 2. اختبار التحميل / Load Test

```bash
# Install Apache Bench (ab) or use similar tool
ab -n 100 -c 10 http://localhost:8000/health
```

---

## اختبارات قاعدة البيانات / Database Tests

### 1. اختبار ChromaDB

```bash
# Check ChromaDB health
curl http://localhost:8001/api/v1/heartbeat

# Expected: {"nanosecond heartbeat": ...}
```

### 2. اختبار Neo4j

```bash
# Open Neo4j Browser
# http://localhost:7474
# Login using the credentials defined in your `.env` file

# Run test query
MATCH (n) RETURN n LIMIT 25
```

### 3. اختبار SQLite

```bash
# Check database files exist
docker exec -it my-ai-advisor-backend-1 ls -la /app/app_data/

# Expected: users.db, progress.db, notifications.db
```

---

## سيناريوهات الاختبار الكاملة / Complete Test Scenarios

### السيناريو 1: تسجيل طالب جديد واستخدام النظام
1. تسجيل طالب جديد
2. تسجيل الدخول
3. جمع البيانات من النظام الجامعي
4. تحليل التقدم
5. استخدام الدردشة الذكية
6. محاكاة المعدل

### السيناريو 2: Admin فهرسة المستندات
1. تسجيل الدخول كـ admin
2. فهرسة المستندات
3. فهرسة الرسم البياني
4. اختبار الدردشة على المستندات المفهرسة

### السيناريو 3: اختبار الوضع التجريبي
1. تسجيل الدخول بالوضع التجريبي
2. محاولة الوصول للميزات الشخصية
3. التحقق من الرسائل التحذيرية

---

## أدوات الاختبار / Testing Tools

### 1. Postman
- استيراد collection من API documentation
- اختبار جميع endpoints

### 2. curl
- اختبار سريع من سطر الأوامر
- مناسب للأتمتة

### 3. pytest (للمستقبل)
```python
# Example test structure
def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
```

---

## قائمة التحقق من الاختبار / Test Checklist

### الوظائف الأساسية
- [ ] تسجيل الدخول
- [ ] تسجيل الخروج
- [ ] تسجيل طالب جديد
- [ ] تسجيل admin جديد
- [ ] الدردشة الذكية
- [ ] تحليل التقدم
- [ ] محاكي المعدل
- [ ] الرسم البياني للمهارات
- [ ] الإشعارات

### الأمان
- [ ] Rate limiting
- [ ] Input validation
- [ ] Authorization checks
- [ ] Security headers
- [ ] SQL injection prevention
- [ ] XSS protection

### الأداء
- [ ] وقت الاستجابة < 5s
- [ ] لا توجد memory leaks
- [ ] قاعدة البيانات تعمل بشكل صحيح

---

## استكشاف الأخطاء أثناء الاختبار / Troubleshooting Tests

### المشكلة: 401 Unauthorized
**الحل:** تحقق من:
- Token صحيح وغير منتهي الصلاحية
- Header Authorization موجود
- Format: `Bearer TOKEN`

### المشكلة: 429 Too Many Requests
**الحل:** انتظر دقيقة ثم حاول مرة أخرى

### المشكلة: 500 Internal Server Error
**الحل:** تحقق من:
- السجلات: `docker-compose logs backend`
- حالة الخدمات: `docker-compose ps`
- قاعدة البيانات متصلة

---

**آخر تحديث / Last Updated:** 2025

