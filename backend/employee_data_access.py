# الموظفون المسموح لهم بقراءة ملخصات Vindora. لا توجد بيانات خام أو صلاحيات كتابة.
EMPLOYEE_DATASETS = {
    "ابراهيم": ("overview", "sales", "products", "finance", "marketers", "suppliers", "support"),
    "اسلام": ("products",),
    "محمد": ("finance", "sales"),
    "ثابت": ("overview", "sales", "products", "finance", "marketers"),
    "كريم": (),  # لا يوجد مصدر حملات إعلانية في قاعدة Vindora الحالية.
    "ياسر": ("overview", "support", "sales"),
    "عمرو": ("suppliers", "products"),
    "هدى": ("marketers", "finance", "sales"),
}

def datasets_for(employee_id: str) -> tuple[str, ...]:
    return EMPLOYEE_DATASETS.get(employee_id, ())
