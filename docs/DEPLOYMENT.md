# دليل النشر الأولي

## GitHub Pages
1. افتح Settings ثم Pages.
2. اختر GitHub Actions للنشر من مجلد `office/`.
3. اضبط `OFFICE_API_URL` في `office/frontend/js/config.js` على رابط الخدمة بعد نشر الـBackend.
4. لا تضع أسرارًا أو مفاتيح خاصة في ملفات JavaScript العامة.

## Bot-Hosting
1. اربط المستودع `aminbodaqa-oss/office-brains-api`.
2. اجعل مجلد التشغيل `backend` إن كانت المنصة تدعم Working Directory.
3. ثبّت الحزم من `requirements.txt`.
4. أمر التشغيل المقترح: `uvicorn main:app --host 0.0.0.0 --port $PORT`.
5. ابدأ بـ `BRAIN_PROVIDER=demo` لاختبار اتصال الـAPI فقط.
6. لا تحوّل إلى `ollama` إلا بعد توفير عنوان نموذج محلي يعمل ويمكن للسيرفر الوصول إليه.
7. أضف `PLATFORM_SECRETS_KEY` كمتغير بيئة سري قبل حفظ مفاتيح AI من لوحة Super Admin. أنشئه بالأمر:
   `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
8. احتفظ بقيمة `PLATFORM_SECRETS_KEY` في مكان آمن ولا تغيّرها بعد تخزين المفاتيح؛ تغييرها يمنع فك تشفير المفاتيح المحفوظة.
9. بعد تشغيل الخدمة، اختر مزود الذكاء الاصطناعي والنموذج من لوحة Super Admin. تُحفظ إعدادات المزود في قاعدة البيانات، وتُشفّر مفاتيح API على السيرفر. متغيرات `BRAIN_PROVIDER` و`GEMINI_API_KEY` تُستخدم كبداية أولية أو كبديل بيئي عند عدم وجود مفتاح محفوظ.

## Website Studio
- الموقع العام موجود في `office/index.html`، وواجهة المكتب في `office/frontend/`، ومركز السوبر أدمن في `office/frontend/platform-admin.html`.
- يقرأ كل سطح إعداداته المنشورة من `GET /api/public/experience?surface=...`؛ المساحات المدعومة: `platform_site` و`office_login` و`office_workspace` و`super_admin`.
- إدارة المسودات والنشر والإصدارات السابقة تتم من مسارات `/api/platform/admin/experiences/*` بعد مصادقة Super Admin.
- تخصيص مكتب عميل محدد يُحفظ بنطاق مستقل باستخدام `customer_workspace` ومعرّف مساحة العمل. لا يُعرض للعميل قبل استكمال وتفعيل تسجيل دخول العملاء وعزل الجلسات.
- الشعار الموحد يُحفظ عبر `/api/platform/admin/branding/logo` ويُستخدم في صور الواجهات وأيقونات المتصفح.
- احفظ التعديلات كمسودة أولًا، راجع المعاينة، ثم انشرها. استعادة إصدار سابق تنشئ مسودة جديدة ولا تستبدل الإصدار المنشور تلقائيًا.

## تنبيه
رسالة `Permission denied` السابقة مرتبطة بإعداد سكربت التثبيت/Startup. راجع إعداد Startup الفعلي قبل إعادة تشغيله. قد تختلف صيغة متغير المنفذ حسب المنصة.


## التشغيل التلقائي للمكتب
- أضف متغير البيئة `AUTONOMOUS_OFFICE_ENABLED=true` في إعدادات خدمة Backend فقط، ولا تضفه إلى ملفات الواجهة.
- يبدأ التشغيل في 09:00 بتوقيت `Africa/Cairo` من الأحد إلى الخميس.
- يجب أن تظل خدمة Backend عاملة؛ هذا الجدول يعمل داخل عملية FastAPI ولا يعمل إذا أوقفت منصة الاستضافة الخدمة أو نامت.
- اختر مزودًا فعليًا من إعدادات الذكاء الاصطناعي في لوحة Super Admin قبل التشغيل. وضع `demo` لا ينشئ تقارير تلقائية.
- يمكن للمالك قراءة الحالة والتقارير عبر `GET /api/automation/status` و`GET /api/automation/reports` مع Bearer token.
- الإصدار الأول ينشئ تقارير الأقسام وملخص المدير فقط؛ لا يعقد اجتماعات فعلية ولا ينفذ مهام تشغيلية تلقائيًا بعد.
