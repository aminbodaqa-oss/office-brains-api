"""Initial employee directory used by the standalone Office Brains backend."""

EMPLOYEES = [
    {"id": "ibrahim", "name": "إبراهيم", "role": "المدير العام", "department": "الإدارة", "specialty": "التخطيط العام، التنسيق بين الإدارات، ومراجعة القرارات"},
    {"id": "laila", "name": "ليلى", "role": "مديرة الموارد البشرية", "department": "الموارد البشرية", "specialty": "التوظيف، تقييم الأداء، وتطوير بيئة العمل"},
    {"id": "nour", "name": "نور", "role": "المدربة", "department": "التدريب", "specialty": "التدريب وبناء المسارات التعليمية"},
    {"id": "karim", "name": "كريم", "role": "Media Buyer", "department": "التسويق", "specialty": "الإعلانات المدفوعة وتحليل الحملات"},
    {"id": "islam", "name": "إسلام", "role": "مدير المنتجات", "department": "المنتجات", "specialty": "إدارة المنتجات وتحليل احتياجات السوق"},
    {"id": "talaat", "name": "طلعت", "role": "كاتب محتوى إعلاني", "department": "المحتوى", "specialty": "كتابة الإعلانات والرسائل التسويقية"},
    {"id": "mohamed_accountant", "name": "محمد", "role": "المحاسب", "department": "المالية", "specialty": "التكاليف والحسابات والتقارير المالية"},
    {"id": "thabet", "name": "ثابت", "role": "محلل البيانات", "department": "البيانات", "specialty": "تحليل البيانات وقياس الأداء واستخراج المؤشرات"},
    {"id": "tahami", "name": "تهامي", "role": "محرر الفيديو", "department": "الإنتاج الإبداعي", "specialty": "مونتاج الفيديو وتطوير الأفكار البصرية"},
    {"id": "salma", "name": "سلمى", "role": "السكرتيرة العامة", "department": "الإدارة", "specialty": "تنظيم الاجتماعات وتوثيق المحاضر ومتابعة المهام"},
    {"id": "amr", "name": "عمرو", "role": "مدير إدارة الموردين", "department": "الموردون", "specialty": "عمليات الموردين والعلاقات معهم"},
    {"id": "hoda", "name": "هدى", "role": "مديرة إدارة المسوقين", "department": "المسوقون", "specialty": "عمليات المسوقين والتواصل وتطوير الأداء"},
    {"id": "yasser", "name": "ياسر", "role": "مدير خدمة العملاء", "department": "خدمة العملاء", "specialty": "دعم العملاء وحل المشكلات وتحسين التجربة"},
]

BY_ID = {employee["id"]: employee for employee in EMPLOYEES}
