Write-Host "🧩 بدء الفحص الشامل لبيئة My AI Advisor..." -ForegroundColor Cyan
Start-Sleep -Seconds 1

# وظيفة لعرض النتيجة بخط واضح
function Show-Step($msg, $color="White") {
    Write-Host "`n=== $msg ===" -ForegroundColor $color
    Start-Sleep -Milliseconds 500
}

# 1️⃣ التحقق من وجود Docker و Compose
Show-Step "التحقق من Docker و Docker Compose" "Yellow"
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Docker غير مثبت أو غير مضاف إلى PATH" -ForegroundColor Red
    pause
    exit
}
if (-not (Get-Command "docker compose" -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Docker Compose غير متوفر" -ForegroundColor Red
    pause
    exit
}
Write-Host "✅ Docker و Compose متوفرين." -ForegroundColor Green

# 2️⃣ التحقق من ملف docker-compose.yml
Show-Step "التحقق من وجود ملف docker-compose.yml" "Yellow"
if (-not (Test-Path ".\docker-compose.yml")) {
    Write-Host "❌ ملف docker-compose.yml غير موجود في هذا المسار!" -ForegroundColor Red
    pause
    exit
}
Write-Host "✅ الملف موجود في $(Get-Location)" -ForegroundColor Green

# 3️⃣ التحقق من وجود مجلد الموديلات
Show-Step "التحقق من مجلد الموديلات" "Yellow"
$modelsPath = "C:\Users\Public\ollama-models"
if (-not (Test-Path $modelsPath)) {
    Write-Host "⚠️ المجلد غير موجود، سيتم إنشاؤه..." -ForegroundColor Yellow
    New-Item -ItemType Directory -Path $modelsPath | Out-Null
}
Write-Host "✅ المجلد موجود: $modelsPath" -ForegroundColor Green

# 4️⃣ التحقق من الملفات داخله
Show-Step "التحقق من الملفات داخل مجلد الموديلات" "Yellow"
$models = Get-ChildItem -Path $modelsPath -Recurse -File
if ($models.Count -gt 0) {
    Write-Host "✅ تم العثور على $($models.Count) ملف موديل داخل المجلد" -ForegroundColor Green
} else {
    Write-Host "⚠️ لا توجد ملفات موديل داخل المجلد" -ForegroundColor Yellow
}

# 5️⃣ التحقق من الشبكة
Show-Step "التحقق من وجود شبكة المشروع" "Yellow"
$networkExists = docker network ls --format "{{.Name}}" | Select-String -Pattern "my-ai-advisor_app-network"
if (-not $networkExists) {
    Write-Host "🔧 إنشاء الشبكة my-ai-advisor_app-network..." -ForegroundColor Yellow
    docker network create my-ai-advisor_app-network | Out-Null
} else {
    Write-Host "✅ الشبكة موجودة." -ForegroundColor Green
}

# 6️⃣ التحقق من وجود الحاوية llm-service
Show-Step "التحقق من وجود الحاوية llm-service" "Yellow"
$llm = docker ps -a --format "{{.Names}}" | Where-Object { $_ -match "llm-service" }
if (-not $llm) {
    Write-Host "🔧 تشغيل الخدمة llm-service..." -ForegroundColor Yellow
    docker compose up -d llm-service
} else {
    Write-Host "✅ الحاوية موجودة." -ForegroundColor Green
    docker start my-ai-advisor-llm-service-1 | Out-Null
}

# 7️⃣ التحقق من حالة الخدمة
Show-Step "التحقق من حالة الحاوية llm-service" "Yellow"
$state = docker inspect -f '{{.State.Status}}' my-ai-advisor-llm-service-1 2>$null
if ($state -eq "running") {
    Write-Host "✅ الخدمة تعمل الآن." -ForegroundColor Green
} else {
    Write-Host "⚠️ الخدمة متوقفة، سيتم إعادة تشغيلها..." -ForegroundColor Yellow
    docker restart my-ai-advisor-llm-service-1 | Out-Null
}

# 8️⃣ التحقق من المجلد داخل الـ container
Show-Step "فحص المجلد داخل الحاوية" "Yellow"
docker exec my-ai-advisor-llm-service-1 ls /root/.ollama/models

# 9️⃣ التحقق من قائمة الموديلات داخل Ollama
Show-Step "فحص الموديلات داخل Ollama" "Yellow"
docker exec my-ai-advisor-llm-service-1 ollama list

Show-Step "✅ تم الانتهاء من الفحص الشامل بنجاح!" "Green"
Write-Host "`nاضغط أي مفتاح للإغلاق..." -ForegroundColor Cyan
pause
