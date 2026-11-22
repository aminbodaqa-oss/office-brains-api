(() => {
  const API = "https://9ywu5lapwb.apps.bot-hosting.cloud";
  const $ = (id) => document.getElementById(id);
  let token = sessionStorage.getItem("office_platform_admin_token") || "";
  const saveToken = (value) => {
    token = value || "";
    if (token) sessionStorage.setItem("office_platform_admin_token", token);
    else sessionStorage.removeItem("office_platform_admin_token");
  };
  let customerSearchTimer = null;

  const number = (value) => Number(value || 0).toLocaleString("ar-EG");
  const put = (id, value) => { const node = $(id); if (node) node.textContent = value; };
  const mark = (id, healthy) => {
    const node = $(id);
    if (!node) return;
    node.classList.toggle("warn", !healthy);
  };

  $("adminLogin").addEventListener("submit", async (event) => {
    event.preventDefault();
    $("loginError").textContent = "";
    const button = $("adminLogin").querySelector("button");
    button.disabled = true;
    try {
      const response = await fetch(API + "/api/platform/admin/login", {
        method: "POST",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify({
          username: $("adminUser").value.trim(),
          password: $("adminPass").value
        }),
        cache: "no-store"
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "تعذر تسجيل الدخول.");
      saveToken(data.access_token);
      $("loginView").classList.add("hidden");
      $("appView").classList.remove("hidden");
      await loadOverview();
      await loadCustomers();
      await loadTenantReadiness();
    } catch (error) {
      $("loginError").textContent = error.message || "حدث خطأ غير متوقع.";
    } finally {
      button.disabled = false;
    }
  });

  async function loadOverview() {
    $("loadError").textContent = "";
    $("refreshBtn").disabled = true;
    try {
      const response = await fetch(API + "/api/platform/admin/overview", {
        headers: {Authorization: "Bearer " + token},
        cache: "no-store"
      });
      const data = await response.json();
      if (response.status === 401) {
        saveToken("");
        $("appView").classList.add("hidden");
        $("loginView").classList.remove("hidden");
        $("adminPass").value = "";
        throw new Error("انتهت الجلسة الإدارية. سجّل الدخول مرة أخرى.");
      }
      if (!response.ok) throw new Error(data.detail || "تعذر تحميل بيانات المنصة.");

      const system = data.system || {};
      const ops = data.operations || {};
      const catalog = data.catalog || {};
      const taskStates = ops.task_status_counts || {};
      const executionStates = ops.execution_status_counts || {};
      const apiOk = data.api?.status === "ok";
      const dbOk = system.database === "ok";
      const aiReady = Boolean(system.provider_ready);
      const authReady = system.admin_auth === "active";
      const engineOn = Boolean(system.automation_enabled);

      put("apiState", apiOk ? "متصل" : "غير متاح");
      put("dbState", dbOk ? "سليمة" : "غير متاحة");
      put("provider", data.api?.provider || "غير محدد");
      put("engineState", engineOn ? "مفعّل" : "متوقف");
      put("tasks", number(ops.tasks_total));
      put("queuedTasks", number(executionStates.queued));
      put("meetings", number(ops.meetings_scheduled));
      put("unreadNotifications", number(ops.notifications_unread));
      put("pushDevices", number(ops.push_devices_active));
      put("employees", number(catalog.employee_templates));

      put("apiHealthText", apiOk ? "يعمل" : "مشكلة");
      put("dbHealthText", dbOk ? "متصلة" : "مشكلة");
      put("aiHealthText", aiReady ? "جاهز" : "غير جاهز");
      put("authHealthText", authReady ? "مفعّلة" : "غير مؤكدة");
      mark("apiHealthDot", apiOk);
      mark("dbHealthDot", dbOk);
      mark("aiHealthDot", aiReady);
      mark("authHealthDot", authReady);

      put("taskOpen", number(taskStates.open));
      put("taskProgress", number(taskStates.in_progress));
      put("taskReview", number(taskStates.review));
      put("taskCompleted", number(taskStates.completed));
      put("taskCancelled", number(taskStates.cancelled));
    } catch (error) {
      $("loadError").textContent = error.message || "تعذر تحميل البيانات.";
    } finally {
      $("refreshBtn").disabled = false;
    }
  }


  async function loadTenantReadiness() {
    const list = $("readinessTable");
    if (!list || !token) return;
    const status = $("readinessStatus");
    list.textContent = "جاري فحص الجداول...";
    status.textContent = "";
    const button = $("refreshTenantReadiness");
    if (button) button.disabled = true;
    try {
      const data = await platformRequest("/api/platform/admin/tenant-readiness");
      const summary = data.summary || {};
      put("readinessFound", number(summary.tenant_tables_found) + " / " + number(summary.tenant_tables_expected));
      put("readinessMissingScope", number(summary.tables_missing_workspace_id));
      put("readinessMissingTables", number(summary.tables_not_initialized));
      put("readinessForeignKeys", number(summary.platform_foreign_key_issues));
      const blocked = !data.tenant_data_schema_ready || Number(summary.platform_foreign_key_issues || 0) > 0;
      status.textContent = blocked
        ? "قاعدة البيانات غير جاهزة للترحيل. راجع الجداول التي تحتاج تجهيزًا."
        : "البنية الأساسية جاهزة للمراجعة النهائية قبل الترحيل.";
      status.classList.toggle("warn", blocked);
      list.replaceChildren();
      (data.tables || []).forEach((item) => {
        const row = document.createElement("div");
        row.className = "readiness-row";
        const name = document.createElement("strong");
        name.textContent = item.table;
        const purpose = document.createElement("span");
        purpose.textContent = item.purpose || "";
        const count = document.createElement("span");
        count.textContent = item.rows === null ? "الجدول غير موجود" : number(item.rows) + " سجل";
        const state = document.createElement("span");
        state.className = item.has_workspace_id ? "readiness-good" : "readiness-warn";
        state.textContent = item.has_workspace_id ? "مرتبط بمساحة عمل" : (item.exists ? "يحتاج workspace_id" : "غير مهيأ");
        row.append(name, purpose, count, state);
        list.append(row);
      });
      const safety = $("readinessSafety");
      if (safety) safety.textContent = (data.guarantees || []).join(" ");
    } catch (error) {
      list.textContent = error.message || "تعذر إجراء الفحص.";
      status.textContent = "تعذر تحميل تقرير الجاهزية.";
      status.classList.add("warn");
    } finally {
      if (button) button.disabled = false;
    }
  }

  const planNames = {trial:"تجريبية",starter:"بداية",professional:"احترافية",business:"أعمال",enterprise:"مؤسسات"};
  const statusNames = {trial:"تجريبي",active:"نشط",suspended:"موقوف"};
  async function platformRequest(path, options = {}) {
    const response = await fetch(API + path, {
      ...options,
      headers: {...(options.headers || {}), Authorization:"Bearer " + token,
        ...(options.body ? {"Content-Type":"application/json"} : {})},
      cache:"no-store"
    });
    const data = await response.json();
    if (response.status === 401) {
      saveToken("");
      $("appView").classList.add("hidden");
      $("loginView").classList.remove("hidden");
      throw new Error("انتهت الجلسة الإدارية. سجّل الدخول مرة أخرى.");
    }
    if (!response.ok) throw new Error(data.detail || "تعذر تنفيذ الطلب.");
    return data;
  }

  async function loadCustomers() {
    const list = $("customerList");
    if (!list || !token) return;
    list.innerHTML = '<p class="muted">جاري تحميل العملاء...</p>';
    try {
      const q = $("customerSearch")?.value.trim() || "";
      const status = $("customerStatus")?.value || "";
      const params = new URLSearchParams();
      if (q) params.set("q", q);
      if (status) params.set("status", status);
      const data = await platformRequest("/api/platform/admin/customers?" + params.toString());
      const totals = data.totals || {};
      put("customerTotal", number(totals.all));
      put("customerTrial", number(totals.trial));
      put("customerActive", number(totals.active));
      put("customerSuspended", number(totals.suspended));
      if (!data.customers?.length) {
        list.innerHTML = '<p class="muted">لا يوجد عملاء مطابقون لبحثك.</p>';
        return;
      }
      list.innerHTML = data.customers.map((customer) => {
        const safe = (value) => String(value || "").replace(/[&<>"']/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char]));
        return '<article class="customer-row"><div class="customer-primary"><strong>'+safe(customer.company_name)+'</strong><span>'+safe(customer.contact_name || "لم يحدد المسؤول")+'</span><small>'+safe(customer.email)+' · '+safe(customer.phone)+'</small></div><div class="customer-meta"><span>الباقة: '+safe(planNames[customer.plan_code] || customer.plan_code)+'</span><span>المساحة: '+safe(customer.workspace_name || customer.company_name)+'</span><span class="status-label '+safe(customer.status)+'">'+safe(statusNames[customer.status] || customer.status)+'</span></div><div class="customer-actions"><select data-plan="'+safe(customer.id)+'" aria-label="تغيير الباقة">'+Object.entries(planNames).map(([key,label])=>'<option value="'+key+'" '+(customer.plan_code===key?'selected':'')+'>'+label+'</option>').join("")+'</select><select data-status="'+safe(customer.id)+'" aria-label="تغيير الحالة">'+Object.entries(statusNames).map(([key,label])=>'<option value="'+key+'" '+(customer.status===key?'selected':'')+'>'+label+'</option>').join("")+'</select><button type="button" data-save-customer="'+safe(customer.id)+'">حفظ</button></div></article>';
      }).join("");
    } catch (error) {
      list.innerHTML = '<p class="error">'+String(error.message || "تعذر تحميل العملاء.")+'</p>';
    }
  }

  $("customerCreateForm")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const submit = form.querySelector('button[type="submit"]');
    const message = $("customerFormMessage");
    submit.disabled = true;
    message.textContent = "جاري إنشاء حساب العميل ومساحة العمل...";
    const values = Object.fromEntries(new FormData(form).entries());
    try {
      const result = await platformRequest("/api/platform/admin/customers", {method:"POST",body:JSON.stringify(values)});
      message.textContent = "تم إنشاء حساب العميل ومساحة العمل بنجاح.";
      form.reset();
      await loadCustomers();
    } catch (error) {
      message.textContent = error.message || "تعذر إنشاء الحساب.";
    } finally {
      submit.disabled = false;
    }
  });

  $("customerList")?.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-save-customer]");
    if (!button) return;
    const id = button.dataset.saveCustomer;
    const status = document.querySelector('[data-status="'+id+'"]')?.value;
    const plan_code = document.querySelector('[data-plan="'+id+'"]')?.value;
    button.disabled = true;
    try {
      await platformRequest("/api/platform/admin/customers/"+encodeURIComponent(id), {
        method:"PATCH",body:JSON.stringify({status,plan_code})
      });
      await loadCustomers();
    } catch (error) {
      alert(error.message || "تعذر تحديث بيانات العميل.");
      button.disabled = false;
    }
  });

  $("loadCustomersBtn")?.addEventListener("click", loadCustomers);
  $("customerStatus")?.addEventListener("change", loadCustomers);
  $("customerSearch")?.addEventListener("input", () => {
    clearTimeout(customerSearchTimer);
    customerSearchTimer = setTimeout(loadCustomers, 250);
  });

  $("refreshTenantReadiness")?.addEventListener("click", loadTenantReadiness);

  $("refreshBtn").addEventListener("click", loadOverview);
  // Restore the admin session after a page refresh in the same browser tab.
  if (token) {
    $("loginView").classList.add("hidden");
    $("appView").classList.remove("hidden");
    loadOverview();
    loadCustomers();
    loadTenantReadiness();
  }

  $("logoutBtn").addEventListener("click", () => {
    saveToken("");
    $("appView").classList.add("hidden");
    $("loginView").classList.remove("hidden");
    $("adminPass").value = "";
  });
})();