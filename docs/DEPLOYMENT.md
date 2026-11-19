# دليل النشر الأولي

## GitHub Pages
1. افتح Settings ثم Pages.
2. اختر GitHub Actions للنشر من مجلد `office/`.
3. اضبط `OFFICE_API_URL` في `office/js/config.js` على رابط الخدمة بعد نشر الـBackend.
4. لا تضع أسرارًا أو مفاتيح خاصة في ملفات JavaScript العامة.

## Bot-Hosting
1. اربط المستودع `aminbodaqa-oss/office-brains-api`.
2. اجعل مجلد التشغيل `backend` إن كانت المنصة تدعم Working Directory.
3. ثبّت الحزم من `requirements.txt`.
4. أمر التشغيل المقترح: `uvicorn main:app --host 0.0.0.0 --port $PORT`.
5. ابدأ بـ `BRAIN_PROVIDER=demo` لاختبار اتصال الـAPI فقط.
6. لا تحوّل إلى `ollama` إلا بعد توفير عنوان نموذج محلي يعمل ويمكن للسيرفر الوصول إليه.

## تنبيه
رسالة `Permission denied` السابقة مرتبطة بإعداد سكربت التثبيت/Startup. راجع إعداد Startup الفعلي قبل إعادة تشغيله. قد تختلف صيغة متغير المنفذ حسب المنصة.
