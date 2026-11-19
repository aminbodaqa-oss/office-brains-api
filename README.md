# Office Brains

مشروع المكتب الذكي: واجهة عربية لإدارة عقول موظفين افتراضيين، مع Backend مستقل باستخدام Python وFastAPI.

## بنية المشروع
- `الواجهة/`: واجهة الويب الثابتة، مخصصة للنشر على GitHub Pages.
- `backend/`: واجهة API وقاعدة البيانات ومنطق الموظفين.
- `docs/`: تعليمات التشغيل والنشر.

## الحالة الحالية
هذه نسخة تأسيسية تجريبية (v0.1). وضع المزود الافتراضي هو `demo`، ولا يعني ذلك وجود نموذج ذكاء اصطناعي فعلي. يمكن إعداد مزود Ollama ذاتي الاستضافة عبر متغيرات البيئة عند توفر خادم مناسب.

## تشغيل Backend محليًا
```bash
cd backend
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

اختبار الصحة: `/health`.

## إعدادات الواجهة
عدّل `الواجهة/js/config.js` بعد نشر الـBackend لوضع رابط API. لا تضع أسرارًا في ملفات الواجهة المنشورة للعامة.

## النشر
راجع `docs/DEPLOYMENT.md`. GitHub Pages يستضيف الواجهة الثابتة فقط، أما Python فيعمل على استضافة Backend منفصلة.
