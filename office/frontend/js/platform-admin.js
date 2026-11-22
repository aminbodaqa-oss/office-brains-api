(() => {
  const API = (window.OFFICE_API_URL || "").replace(/\/$/, "");
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
      if (location.hash === "#website-studio") await loadExperienceStudio();
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
        return '<article class="customer-row"><div class="customer-primary"><strong>'+safe(customer.company_name)+'</strong><span>'+safe(customer.contact_name || "لم يحدد المسؤول")+'</span><small>'+safe(customer.email)+' · '+safe(customer.phone)+'</small></div><div class="customer-meta"><span>الباقة: '+safe(planNames[customer.plan_code] || customer.plan_code)+'</span><span>المساحة: '+safe(customer.workspace_name || customer.company_name)+'</span><span class="status-label '+safe(customer.status)+'">'+safe(statusNames[customer.status] || customer.status)+'</span></div><div class="customer-actions"><select data-plan="'+safe(customer.id)+'" aria-label="تغيير الباقة">'+Object.entries(planNames).map(([key,label])=>'<option value="'+key+'" '+(customer.plan_code===key?'selected':'')+'>'+label+'</option>').join("")+'</select><select data-status="'+safe(customer.id)+'" aria-label="تغيير الحالة">'+Object.entries(statusNames).map(([key,label])=>'<option value="'+key+'" '+(customer.status===key?'selected':'')+'>'+label+'</option>').join("")+'</select><button type="button" data-save-customer="'+safe(customer.id)+'">حفظ</button><button type="button" class="ghost" data-view-customer="'+safe(customer.id)+'">التفاصيل</button></div></article>';
      }).join("");
    } catch (error) {
      list.innerHTML = '<p class="error">'+String(error.message || "تعذر تحميل العملاء.")+'</p>';
    }
  }

  async function loadCustomerDetails(customerId) {
    const panel = $("customerDetails");
    if (!panel) return;
    panel.classList.remove("hidden");
    $("customerDetailsTitle").textContent = "جاري تحميل بيانات العميل...";
    $("customerDetailsGrid").replaceChildren();
    $("customerAuditList").textContent = "جاري تحميل سجل التغييرات...";
    try {
      const data = await platformRequest("/api/platform/admin/customers/" + encodeURIComponent(customerId));
      const customer = data.customer || {};
      const workspace = data.workspace || {};
      $("customerDetailsTitle").textContent = customer.company_name || "تفاصيل العميل";
      const fields = [
        ["المسؤول", customer.contact_name || "غير محدد"],
        ["البريد الإلكتروني", customer.email || "—"],
        ["رقم الهاتف", customer.phone || "—"],
        ["الباقة", planNames[customer.plan_code] || customer.plan_code || "—"],
        ["حالة العميل", statusNames[customer.status] || customer.status || "—"],
        ["معرّف العميل", customer.id || "—"],
        ["اسم مساحة العمل", workspace.name || "—"],
        ["حالة مساحة العمل", statusNames[workspace.status] || workspace.status || "—"],
        ["الأعضاء المسجلون", number(workspace.memberships)],
        ["دخول العملاء", workspace.customer_access_enabled ? "مفعّل" : "غير مفعّل"],
        ["تاريخ الإنشاء", customer.created_at ? new Date(customer.created_at).toLocaleString("ar-EG") : "—"],
        ["آخر تحديث", customer.updated_at ? new Date(customer.updated_at).toLocaleString("ar-EG") : "—"]
      ];
      const grid = $("customerDetailsGrid");
      fields.forEach(([label, value]) => {
        const item = document.createElement("article");
        const name = document.createElement("span");
        const text = document.createElement("strong");
        name.textContent = label;
        text.textContent = String(value);
        item.append(name, text);
        grid.append(item);
      });
      const auditList = $("customerAuditList");
      auditList.replaceChildren();
      const events = data.audit || [];
      if (!events.length) {
        auditList.textContent = "لا توجد تغييرات مسجلة لهذا الحساب حتى الآن.";
      } else {
        events.forEach((event) => {
          const row = document.createElement("div");
          row.className = "customer-audit-row";
          const action = document.createElement("strong");
          action.textContent = event.action || "تحديث";
          const meta = document.createElement("span");
          const when = event.created_at ? new Date(event.created_at).toLocaleString("ar-EG") : "";
          meta.textContent = [event.actor, when].filter(Boolean).join(" · ");
          row.append(action, meta);
          auditList.append(row);
        });
      }
      panel.scrollIntoView({behavior:"smooth",block:"start"});
    } catch (error) {
      $("customerDetailsTitle").textContent = "تعذر تحميل تفاصيل العميل";
      $("customerDetailsGrid").textContent = error.message || "حدث خطأ أثناء تحميل البيانات.";
      $("customerAuditList").textContent = "";
    }
  }

  $("closeCustomerDetails")?.addEventListener("click", () => $("customerDetails")?.classList.add("hidden"));

  $("customerCreateForm")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const submit = form.querySelector('button[type="submit"]');
    const message = $("customerFormMessage");
    submit.disabled = true;
    message.textContent = "جاري إضافة سجل العميل ومساحة العمل...";
    const values = Object.fromEntries(new FormData(form).entries());
    try {
      const result = await platformRequest("/api/platform/admin/customers", {method:"POST",body:JSON.stringify(values)});
      message.textContent = "تمت إضافة سجل العميل ومساحة العمل بنجاح.";
      form.reset();
      await loadCustomers();
    } catch (error) {
      message.textContent = error.message || "تعذر إنشاء الحساب.";
    } finally {
      submit.disabled = false;
    }
  });

  $("customerList")?.addEventListener("click", async (event) => {
    const detailsButton = event.target.closest("[data-view-customer]");
    if (detailsButton) {
      await loadCustomerDetails(detailsButton.dataset.viewCustomer);
      return;
    }
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

  async function loadAISettings() {
    const message = $("aiSettingsMessage");
    try {
      const data = await platformRequest("/api/platform/admin/ai-settings");
      const form = $("aiSettingsForm");
      if (!form) return;
      form.elements.provider.value = data.provider || "demo";
      form.elements.model.value = data.model || "gemini-3.8-flash";
      form.elements.base_url.value = data.base_url || "";
      form.elements.timeout_seconds.value = data.timeout_seconds || 90;
      form.elements.fallback_provider.value = data.fallback_provider || "demo";
      form.elements.fallback_model.value = data.fallback_model || "";
      form.elements.fallback_base_url.value = data.fallback_base_url || "";
      form.elements.api_key.value = "";
      form.elements.clear_api_key.checked = false;
      $("aiKeyStatus").textContent = data.has_api_key
        ? "مفتاح محفوظ (" + data.key_source + ")"
        : "لا يوجد مفتاح محفوظ";
      $("aiKeyStatus").className = data.has_api_key ? "billing-active" : "billing-inactive";
      if (message) message.textContent = "";
    } catch (error) {
      if (message) message.textContent = error.message || "تعذر تحميل إعدادات الذكاء الاصطناعي.";
    }
  }

  async function loadPlatformTeam() {
    const list = $("platformTeamList");
    if (!list || !token) return;
    list.textContent = "جاري تحميل دليل الفريق...";
    try {
      const data = await platformRequest("/api/platform/admin/team");
      list.replaceChildren();
      (data.employees || []).forEach(employee => {
        const card = document.createElement("article");
        card.className = "platform-team-card";
        const name = document.createElement("strong");
        name.textContent = employee.id;
        const role = document.createElement("span");
        role.textContent = employee.role;
        const dept = document.createElement("small");
        dept.textContent = employee.department;
        card.append(name, role, dept);
        if ((employee.specialties || []).length) {
          const specialty = document.createElement("p");
          specialty.textContent = "التخصصات: " + employee.specialties.join(" · ");
          card.append(specialty);
        }
        const details = document.createElement("details");
        details.className = "team-edit-details";
        const summary = document.createElement("summary");
        summary.textContent = "تعديل بيانات الدور";
        const form = document.createElement("form");
        form.className = "team-edit-form";
        const roleLabel = document.createElement("label");
        roleLabel.textContent = "المسمى الوظيفي";
        const roleInput = document.createElement("input");
        roleInput.name = "role";
        roleInput.maxLength = 160;
        roleInput.required = true;
        roleInput.value = employee.role || "";
        roleLabel.append(roleInput);
        const deptLabel = document.createElement("label");
        deptLabel.textContent = "القسم";
        const deptInput = document.createElement("input");
        deptInput.name = "department";
        deptInput.maxLength = 160;
        deptInput.required = true;
        deptInput.value = employee.department || "";
        deptLabel.append(deptInput);
        const instructionsLabel = document.createElement("label");
        instructionsLabel.textContent = "التعليمات الإضافية للموظف";
        const instructions = document.createElement("textarea");
        instructions.name = "instructions";
        instructions.maxLength = 6000;
        instructions.rows = 5;
        instructions.value = employee.additional_instructions || "";
        instructions.placeholder = "تعليمات تخصصية إضافية توجه سلوك الموظف";
        instructionsLabel.append(instructions);
        const save = document.createElement("button");
        save.type = "submit";
        save.textContent = "حفظ التعديلات";
        const status = document.createElement("small");
        status.setAttribute("role", "status");
        form.append(roleLabel,deptLabel,instructionsLabel,save,status);
        form.addEventListener("submit", async event => {
          event.preventDefault();
          save.disabled = true;
          status.textContent = "جاري الحفظ...";
          try {
            await platformRequest("/api/platform/admin/team/" + encodeURIComponent(employee.id), {
              method:"PATCH",
              body:JSON.stringify({
                role:roleInput.value.trim(),
                department:deptInput.value.trim(),
                instructions:instructions.value
              })
            });
            status.textContent = "تم حفظ بيانات الموظف.";
            await loadPlatformTeam();
          } catch (error) {
            status.textContent = error.message || "تعذر حفظ بيانات الموظف.";
            save.disabled = false;
          }
        });
        details.append(summary,form);
        card.append(details);
        list.append(card);
      });
      if (!list.children.length) list.textContent = "لا يوجد موظفون معرفون.";
    } catch (error) {
      list.textContent = error.message || "تعذر تحميل دليل الفريق.";
    }
  }

  $("aiSettingsForm")?.addEventListener("submit", async event => {
    event.preventDefault();
    const form = event.currentTarget;
    const button = form.querySelector('button[type="submit"]');
    const message = $("aiSettingsMessage");
    button.disabled = true;
    if (message) message.textContent = "جاري حفظ الإعدادات...";
    try {
      const payload = {
        provider:form.elements.provider.value,
        model:form.elements.model.value.trim(),
        base_url:form.elements.base_url.value.trim(),
        timeout_seconds:Number(form.elements.timeout_seconds.value),
        api_key:form.elements.api_key.value || null,
        clear_api_key:form.elements.clear_api_key.checked
      };
      const data = await platformRequest("/api/platform/admin/ai-settings", {
        method:"PUT", body:JSON.stringify(payload)
      });
      form.elements.api_key.value = "";
      form.elements.clear_api_key.checked = false;
      $("aiKeyStatus").textContent = data.has_api_key
        ? "مفتاح محفوظ (" + data.key_source + ")"
        : "لا يوجد مفتاح محفوظ";
      $("aiKeyStatus").className = data.has_api_key ? "billing-active" : "billing-inactive";
      if (message) message.textContent = "تم حفظ الإعدادات. اختبر الاتصال للتأكد من عمل المزود.";
    } catch (error) {
      if (message) message.textContent = error.message || "تعذر حفظ الإعدادات.";
    } finally {
      button.disabled = false;
    }
  });

  $("testAIConnection")?.addEventListener("click", async () => {
    const button = $("testAIConnection");
    const message = $("aiSettingsMessage");
    button.disabled = true;
    if (message) message.textContent = "جاري إرسال طلب اختبار فعلي إلى المزود...";
    try {
      const data = await platformRequest("/api/platform/admin/ai-settings/test", {method:"POST"});
      if (message) message.textContent = "نجح الاتصال بالمزود " + data.provider + " · رد الاختبار: " + data.response;
    } catch (error) {
      if (message) message.textContent = error.message || "فشل اختبار الاتصال.";
    } finally {
      button.disabled = false;
    }
  });

  $("refreshTeamBtn")?.addEventListener("click", loadPlatformTeam);

  const billingStatusNames = {
    pending_payment:"بانتظار الدفع", active:"نشط", past_due:"متأخر",
    cancelled:"ملغي", expired:"منتهي"
  };
  let billingPlans = [];
  const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, char =>
    ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char]));
  const money = (minor) => (Number(minor || 0) / 100).toLocaleString("ar-EG", {
    style:"currency",currency:"EGP",maximumFractionDigits:2
  });

  async function loadBillingPlans() {
    const data = await platformRequest("/api/platform/admin/plans");
    billingPlans = data.plans || [];
    const catalog = $("planCatalog");
    if (catalog) {
      catalog.replaceChildren();
      billingPlans.forEach((plan) => {
        const card = document.createElement("article");
        card.className = "billing-plan-card";
        const title = document.createElement("h3");
        title.textContent = plan.name;
        const code = document.createElement("small");
        code.textContent = plan.code;
        const desc = document.createElement("p");
        desc.textContent = plan.description || "بدون وصف";
        const price = document.createElement("p");
        price.textContent = "شهري: " + money(plan.monthly_price_minor) + " · سنوي: " + money(plan.yearly_price_minor);
        const state = document.createElement("span");
        state.className = plan.active ? "billing-active" : "billing-inactive";
        state.textContent = plan.active ? "متاحة للاشتراك" : "غير مفعّلة";
        const limits = document.createElement("small");
        limits.textContent = "الحدود: " + JSON.stringify(plan.limits || {});
        const edit = document.createElement("button");
        edit.type = "button";
        edit.className = "ghost";
        edit.textContent = "تعديل الباقة";
        edit.addEventListener("click", () => {
          const form = $("planForm");
          form.elements.code.value = plan.code;
          form.elements.code.readOnly = true;
          form.elements.name.value = plan.name;
          form.elements.description.value = plan.description || "";
          form.elements.monthly_price.value = (Number(plan.monthly_price_minor || 0) / 100).toFixed(2);
          form.elements.yearly_price.value = (Number(plan.yearly_price_minor || 0) / 100).toFixed(2);
          form.elements.limits.value = JSON.stringify(plan.limits || {}, null, 2);
          form.elements.active.checked = Boolean(plan.active);
          $("planFormMessage").textContent = "تعديل الباقة: " + plan.name;
          form.scrollIntoView({behavior:"smooth",block:"center"});
        });
        card.append(title,code,desc,price,state,limits,edit);
        catalog.append(card);
      });
    }
    const select = $("subscriptionPlan");
    if (select) {
      const active = billingPlans.filter(plan => plan.active);
      select.innerHTML = '<option value="">اختر الباقة</option>' + active.map(plan =>
        '<option value="' + escapeHtml(plan.code) + '">' + escapeHtml(plan.name) +
        ' · ' + money(plan.monthly_price_minor) + ' شهري</option>').join("");
    }
  }

  async function loadSubscriptionCustomers() {
    const data = await platformRequest("/api/platform/admin/customers");
    const select = $("subscriptionCustomer");
    if (!select) return;
    select.innerHTML = '<option value="">اختر العميل</option>' + (data.customers || []).map(customer =>
      '<option value="' + escapeHtml(customer.id) + '">' +
      escapeHtml(customer.company_name) + ' · ' + escapeHtml(customer.email) + '</option>').join("");
  }

  async function loadSubscriptions() {
    const list = $("subscriptionList");
    if (!list || !token) return;
    list.textContent = "جاري تحميل الاشتراكات...";
    try {
      const status = $("subscriptionStatusFilter")?.value || "";
      const data = await platformRequest("/api/platform/admin/subscriptions" +
        (status ? "?status=" + encodeURIComponent(status) : ""));
      const items = data.subscriptions || [];
      if (!items.length) {
        list.textContent = "لا توجد اشتراكات في هذه القائمة.";
        return;
      }
      list.replaceChildren();
      items.forEach((item) => {
        const row = document.createElement("article");
        row.className = "subscription-row";
        const info = document.createElement("div");
        const title = document.createElement("strong");
        title.textContent = item.company_name + " · " + item.plan_name;
        const meta = document.createElement("span");
        meta.textContent = (item.billing_cycle === "yearly" ? "سنوي" : "شهري") +
          " · " + money(item.amount_minor) + " · " + new Date(item.starts_at).toLocaleDateString("ar-EG") +
          " حتى " + new Date(item.ends_at).toLocaleDateString("ar-EG");
        const statusNode = document.createElement("span");
        statusNode.className = "status-label " + item.status;
        statusNode.textContent = billingStatusNames[item.status] || item.status;
        const payment = document.createElement("small");
        payment.textContent = "الدفع: " + (item.payment_status === "paid" ? "مدفوع" :
          item.payment_status === "refunded" ? "مسترد" : "غير مدفوع");
        info.append(title,meta,statusNode,payment);
        const actions = document.createElement("div");
        actions.className = "subscription-actions";
        if (item.payment_status !== "paid" && item.status === "pending_payment") {
          const paid = document.createElement("button");
          paid.type = "button";
          paid.textContent = "تأكيد استلام الدفع";
          paid.addEventListener("click", async () => {
            if (!confirm("تأكيد استلام المبلغ يدويًا لهذا الاشتراك؟")) return;
            paid.disabled = true;
            try {
              await platformRequest("/api/platform/admin/subscriptions/" + encodeURIComponent(item.id), {
                method:"PATCH",body:JSON.stringify({payment_status:"paid"})
              });
              await loadSubscriptions();
              await loadCustomers();
            } catch (error) { alert(error.message || "تعذر تحديث الدفع."); paid.disabled = false; }
          });
          actions.append(paid);
        }
        if (!["cancelled","expired"].includes(item.status)) {
          const cancel = document.createElement("button");
          cancel.type = "button";
          cancel.className = "ghost";
          cancel.textContent = "إلغاء الاشتراك";
          cancel.addEventListener("click", async () => {
            if (!confirm("هل تريد إلغاء هذا الاشتراك؟")) return;
            cancel.disabled = true;
            try {
              await platformRequest("/api/platform/admin/subscriptions/" + encodeURIComponent(item.id), {
                method:"PATCH",body:JSON.stringify({status:"cancelled"})
              });
              await loadSubscriptions();
              await loadCustomers();
            } catch (error) { alert(error.message || "تعذر إلغاء الاشتراك."); cancel.disabled = false; }
          });
          actions.append(cancel);
        }
        row.append(info,actions);
        list.append(row);
      });
    } catch (error) {
      list.textContent = error.message || "تعذر تحميل الاشتراكات.";
    }
  }

  $("planForm")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const button = form.querySelector('button[type="submit"]');
    const message = $("planFormMessage");
    button.disabled = true;
    try {
      let limits;
      try { limits = JSON.parse(form.elements.limits.value || "{}"); }
      catch { throw new Error("صيغة حدود الاستخدام يجب أن تكون JSON صحيحة."); }
      if (!limits || Array.isArray(limits) || typeof limits !== "object") {
        throw new Error("حدود الاستخدام يجب أن تكون كائن JSON.");
      }
      const payload = {
        code:form.elements.code.value.trim(), name:form.elements.name.value.trim(),
        description:form.elements.description.value.trim(),
        monthly_price_minor:Math.round(Number(form.elements.monthly_price.value) * 100),
        yearly_price_minor:Math.round(Number(form.elements.yearly_price.value) * 100),
        limits, active:form.elements.active.checked
      };
      await platformRequest("/api/platform/admin/plans", {method:"POST",body:JSON.stringify(payload)});
      message.textContent = "تم حفظ الباقة.";
      form.reset(); form.elements.code.readOnly = false; form.elements.limits.value = "{}";
      await loadBillingPlans();
    } catch (error) { message.textContent = error.message || "تعذر حفظ الباقة."; }
    finally { button.disabled = false; }
  });

  $("resetPlanForm")?.addEventListener("click", () => {
    $("planForm").reset();
    $("planForm").elements.code.readOnly = false;
    $("planForm").elements.limits.value = "{}";
    $("planFormMessage").textContent = "";
  });

  $("subscriptionForm")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const button = form.querySelector('button[type="submit"]');
    const message = $("subscriptionFormMessage");
    button.disabled = true;
    try {
      const starts = form.elements.starts_at.value;
      const payload = {
        customer_id:form.elements.customer_id.value,
        plan_code:form.elements.plan_code.value,
        billing_cycle:form.elements.billing_cycle.value,
        starts_at:starts ? new Date(starts + "T00:00:00").toISOString() : null,
        notes:form.elements.notes.value.trim()
      };
      await platformRequest("/api/platform/admin/subscriptions", {method:"POST",body:JSON.stringify(payload)});
      message.textContent = "تم إنشاء الاشتراك في انتظار تأكيد الدفع.";
      form.reset();
      await loadSubscriptions();
    } catch (error) { message.textContent = error.message || "تعذر إنشاء الاشتراك."; }
    finally { button.disabled = false; }
  });

  $("refreshBillingBtn")?.addEventListener("click", async () => {
    try { await loadBillingPlans(); await loadSubscriptionCustomers(); await loadSubscriptions(); }
    catch (error) { $("planFormMessage").textContent = error.message || "تعذر تحديث بيانات الاشتراكات."; }
  });
  $("subscriptionStatusFilter")?.addEventListener("change", loadSubscriptions);

  async function loadPlatformOperations() {
    const healthGrid = $("opsHealthGrid");
    const countsGrid = $("opsCountsGrid");
    const auditList = $("opsAuditList");
    if (!healthGrid || !token) return;
    healthGrid.textContent = "جاري فحص المنصة...";
    try {
      const data = await platformRequest("/api/platform/admin/operations");
      const health = data.health || {};
      healthGrid.replaceChildren();
      const healthItems = [
        ["واجهة API",health.api === "ok" ? "تعمل" : "تحتاج مراجعة",health.api === "ok"],
        ["قاعدة البيانات",health.database === "ok" ? "متصلة" : "تحتاج مراجعة",health.database === "ok"],
        ["محرك الذكاء",health.ai_ready ? "مزود فعلي: " + health.ai_provider : "وضع التجربة",health.ai_ready],
        ["التشغيل التلقائي",health.automation_enabled ? "مفعّل" : "متوقف",health.automation_enabled]
      ];
      healthItems.forEach(([label,value,ok]) => {
        const card = document.createElement("article");
        card.className = "ops-status-card";
        const heading = document.createElement("small");
        heading.textContent = label;
        const state = document.createElement("strong");
        state.textContent = value;
        state.classList.toggle("ops-good",Boolean(ok));
        state.classList.toggle("ops-warn",!ok);
        card.append(heading,state);
        healthGrid.append(card);
      });
      const statusLabels = {
        trial:"تجريبي",active:"نشط",suspended:"موقوف",
        pending_payment:"بانتظار الدفع",past_due:"متأخر",
        cancelled:"ملغي",expired:"منتهي"
      };
      countsGrid.replaceChildren();
      [["العملاء",data.customers_by_status || {}],["الاشتراكات",data.subscriptions_by_status || {}]].forEach(([title,items]) => {
        const card = document.createElement("article");
        card.className = "ops-count-card";
        const heading = document.createElement("strong");
        heading.textContent = title;
        card.append(heading);
        Object.entries(items).forEach(([key,count]) => {
          const line = document.createElement("div");
          line.className = "ops-count-line";
          const label = document.createElement("span");
          label.textContent = statusLabels[key] || key;
          const numberNode = document.createElement("b");
          numberNode.textContent = number(count);
          line.append(label,numberNode);
          card.append(line);
        });
        if (!Object.keys(items).length) {
          const empty = document.createElement("small");
          empty.textContent = "لا توجد سجلات بعد.";
          card.append(empty);
        }
        countsGrid.append(card);
      });
      auditList.replaceChildren();
      const auditNames = {
        ai_provider_settings_updated:"تحديث إعدادات الذكاء الاصطناعي",
        platform_employee_profile_updated:"تعديل بيانات موظف",
        website_branding_updated:"تحديث هوية ومحتوى الموقع",
        plan_saved:"حفظ باقة"
      };
      (data.audit_log || []).forEach(item => {
        const row = document.createElement("article");
        row.className = "ops-audit-row";
        const details = document.createElement("div");
        const action = document.createElement("strong");
        action.textContent = auditNames[item.action] || item.action;
        const meta = document.createElement("small");
        meta.textContent = item.entity_type + " · " + item.entity_id + " · " + item.actor;
        const date = document.createElement("time");
        const parsed = new Date(item.created_at);
        date.textContent = Number.isNaN(parsed.getTime()) ? item.created_at : parsed.toLocaleString("ar-EG");
        details.append(action,meta);
        row.append(details,date);
        auditList.append(row);
      });
      if (!auditList.children.length) auditList.textContent = "لا توجد تغييرات مسجلة حتى الآن.";
    } catch (error) {
      healthGrid.textContent = error.message || "تعذر تحميل مؤشرات التشغيل.";
    }
  }

  $("refreshOperations")?.addEventListener("click", loadPlatformOperations);

  $("refreshTenantReadiness")?.addEventListener("click", loadTenantReadiness);
  $("siteLogoForm")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget, file = $("siteLogoFile")?.files?.[0], message = $("siteLogoMessage");
    if (!file) { message.textContent = "اختار ملف الشعار الأول."; return; }
    if (!["image/png","image/jpeg","image/webp"].includes(file.type)) { message.textContent = "الصيغ المدعومة PNG وJPG وWEBP فقط."; return; }
    if (file.size > 2 * 1024 * 1024) { message.textContent = "حجم الصورة أكبر من 2 ميجابايت."; return; }
    const button = form.querySelector('button[type="submit"]'); button.disabled = true; message.textContent = "جاري حفظ الشعار...";
    try {
      const dataUrl = await new Promise((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(String(reader.result || "")); reader.onerror = () => reject(new Error("تعذر قراءة ملف الصورة.")); reader.readAsDataURL(file); });
      await platformRequest("/api/platform/admin/branding/logo", {method:"POST", body:JSON.stringify({data_url:dataUrl})});
      document.querySelectorAll("[data-brand-logo]").forEach(img => { img.src = dataUrl; });
      document.querySelectorAll("[data-brand-icon]").forEach(icon => { icon.href = dataUrl; });
      $("siteLogoPreview").src = dataUrl; message.textContent = "تم حفظ الشعار وتطبيقه على صفحات المنصة."; form.reset();
    } catch (error) { message.textContent = error.message || "تعذر حفظ الشعار."; }
    finally { button.disabled = false; }
  });




  const experienceSurfaceNames = {
    platform_site:"الموقع التعريفي العام", office_login:"صفحات الدخول",
    office_workspace:"المكتب ومساحة العمل", super_admin:"مركز السوبر أدمن",
    customer_workspace:"مكتب عميل محدد"
  };
  function experienceScope() {
    const surface = $("experienceSurface")?.value || "platform_site";
    const workspaceId = surface === "customer_workspace" ? $("experienceWorkspaceId")?.value.trim() || "" : "";
    return {surface, workspace_id:workspaceId};
  }
  function experienceFormConfig() {
    const form = $("experienceForm");
    const value = name => form.elements[name]?.value ?? "";
    let navigation, pages;
    try { navigation = JSON.parse(value("navigation_json") || "[]"); }
    catch (_) { throw new Error("صيغة القائمة الرئيسية JSON غير صحيحة."); }
    try { pages = JSON.parse(value("pages_json") || "{}"); }
    catch (_) { throw new Error("صيغة تعريف الصفحات JSON غير صحيحة."); }
    return {
      site_name:value("site_name"), page_title:value("page_title"), meta_description:value("meta_description"),
      headline:value("headline"), headline_emphasis:value("headline_emphasis"), subtitle:value("subtitle"),
      primary_cta_text:value("primary_cta_text"), primary_cta_url:value("primary_cta_url"),
      footer_text:value("footer_text"), welcome_title:value("welcome_title"), welcome_message:value("welcome_message"),
      login_title:value("login_title"), login_message:value("login_message"), sidebar_title:value("sidebar_title"),
      theme:{primary:value("color_primary"),accent:value("color_accent"),highlight:value("color_highlight"),
        background:value("color_background"),surface:value("color_surface"),text:value("color_text")},
      font_family:value("font_family"),density:value("density"),corner_style:value("corner_style"),
      navigation,pages
    };
  }
  function paintExperiencePreview() {
    const form = $("experienceForm");
    if (!form) return;
    const config = experienceFormConfig();
    const scope = experienceScope();
    put("previewSiteName",config.site_name || "Office Brains");
    put("previewSurfaceName",experienceSurfaceNames[scope.surface] || scope.surface);
    put("previewHeadline",config.headline || config.login_title || config.welcome_title || "عنوان الواجهة يظهر هنا");
    put("previewEmphasis",config.headline_emphasis || config.sidebar_title || "");
    put("previewSubtitle",config.subtitle || config.login_message || config.welcome_message || "وصف الواجهة سيظهر هنا عند الكتابة.");
    put("previewFooter",config.footer_text || "Office Brains");
    const preview=$("experiencePreview");
    preview.style.setProperty("--preview-accent",config.theme.accent || "#00A884");
    preview.style.setProperty("--preview-bg",config.theme.background || "#0B1020");
    preview.style.setProperty("--preview-surface",config.theme.surface || "#131B31");
    preview.style.setProperty("--preview-text",config.theme.text || "#F6F7FF");
    $("previewCta").textContent=config.primary_cta_text || "زر الإجراء الرئيسي";
  }
  function populateExperienceForm(config) {
    const form=$("experienceForm"), theme=config.theme || {};
    const mapping={
      site_name:"site_name",page_title:"page_title",meta_description:"meta_description",
      headline:"headline",headline_emphasis:"headline_emphasis",subtitle:"subtitle",
      primary_cta_text:"primary_cta_text",primary_cta_url:"primary_cta_url",footer_text:"footer_text",
      welcome_title:"welcome_title",welcome_message:"welcome_message",login_title:"login_title",
      login_message:"login_message",sidebar_title:"sidebar_title",font_family:"font_family",
      density:"density",corner_style:"corner_style"
    };
    Object.entries(mapping).forEach(([field,key])=>{form.elements[field].value=config[key] ?? "";});
    ["primary","accent","highlight","background","surface","text"].forEach(key=>{
      form.elements["color_"+key].value=theme[key] || ({primary:"#172A3A",accent:"#00A884",highlight:"#F2B84B",background:"#0B1020",surface:"#131B31",text:"#F6F7FF"}[key]);
    });
    form.elements.navigation_json.value=JSON.stringify(config.navigation || [],null,2);
    form.elements.pages_json.value=JSON.stringify(config.pages || {},null,2);
    paintExperiencePreview();
  }
  async function loadExperienceRevisions() {
    const scope=experienceScope(), select=$("experienceRevision");
    if(scope.surface==="customer_workspace" && !scope.workspace_id){select.innerHTML='<option value="">أدخل معرّف مساحة العمل</option>';return;}
    const query=new URLSearchParams({surface:scope.surface});
    if(scope.workspace_id)query.set("workspace_id",scope.workspace_id);
    const data=await platformRequest("/api/platform/admin/experiences/revisions?"+query.toString());
    select.replaceChildren();
    if(!data.revisions?.length){const option=document.createElement("option");option.value="";option.textContent="لا توجد إصدارات منشورة";select.append(option);return;}
    data.revisions.forEach(item=>{
      const option=document.createElement("option");option.value=String(item.version);
      option.textContent="الإصدار "+item.version+" · "+new Date(item.published_at).toLocaleString("ar-EG");
      select.append(option);
    });
  }
  async function loadExperienceStudio() {
    const scope=experienceScope(), message=$("experienceMessage");
    $("experienceWorkspaceWrap").classList.toggle("hidden",scope.surface!=="customer_workspace");
    if(scope.surface==="customer_workspace" && !scope.workspace_id){
      $("experienceScopeNote").textContent="أدخل معرّف مساحة العمل لتحميل إعداداتها المستقلة.";
      $("experienceStatus").textContent="بانتظار المعرّف";
      return;
    }
    const query=new URLSearchParams({surface:scope.surface});
    if(scope.workspace_id)query.set("workspace_id",scope.workspace_id);
    const button=$("loadExperienceBtn");button.disabled=true;
    try{
      const data=await platformRequest("/api/platform/admin/experiences?"+query.toString());
      populateExperienceForm(data.draft || {});
      put("experienceVersion",data.version || 0);
      put("experienceStatus",data.status==="published"?"منشور":data.status==="draft"?"مسودة":"الإعدادات الافتراضية");
      put("experienceState",data.status==="published"?"يوجد إصدار منشور":data.status==="draft"?"توجد مسودة":"لم يتم النشر بعد");
      $("experienceScopeNote").textContent="أنت تعدّل: "+experienceSurfaceNames[scope.surface]+(scope.workspace_id?" · "+scope.workspace_id:"")+".";
      await loadExperienceRevisions();
      if(message)message.textContent="";
    }catch(error){if(message)message.textContent=error.message || "تعذر تحميل إعدادات الواجهة.";}
    finally{button.disabled=false;}
  }
  $("experienceForm")?.addEventListener("input",()=>{
    try{paintExperiencePreview();}catch(error){put("experienceMessage",error.message);}
  });
  $("experienceForm")?.addEventListener("submit",async event=>{
    event.preventDefault();const button=$("saveExperienceDraft"),message=$("experienceMessage");
    const scope=experienceScope();
    if(scope.surface==="customer_workspace"&&!scope.workspace_id){message.textContent="أدخل معرّف مساحة العمل أولًا.";return;}
    button.disabled=true;message.textContent="جاري حفظ المسودة...";
    try{
      const config=experienceFormConfig();
      await platformRequest("/api/platform/admin/experiences/draft",{method:"PUT",body:JSON.stringify({...scope,config})});
      message.textContent="تم حفظ المسودة. لم يتم نشرها على الواجهة العامة.";
      await loadExperienceStudio();
    }catch(error){message.textContent=error.message || "تعذر حفظ المسودة.";}
    finally{button.disabled=false;}
  });
  $("publishExperience")?.addEventListener("click",async()=>{
    const scope=experienceScope(),message=$("experienceMessage"),button=$("publishExperience");
    if(scope.surface==="customer_workspace"&&!scope.workspace_id){message.textContent="أدخل معرّف مساحة العمل أولًا.";return;}
    if(!window.confirm("تأكيد نشر إعدادات "+experienceSurfaceNames[scope.surface]+"؟"))return;
    button.disabled=true;message.textContent="جاري نشر الإصدار...";
    try{
      await platformRequest("/api/platform/admin/experiences/draft",{method:"PUT",body:JSON.stringify({...scope,config:experienceFormConfig()})});
      const result=await platformRequest("/api/platform/admin/experiences/publish",{method:"POST",body:JSON.stringify(scope)});
      message.textContent="تم نشر الإصدار رقم "+result.version+".";
      await loadExperienceStudio();
    }catch(error){message.textContent=error.message || "تعذر نشر الإصدار.";}
    finally{button.disabled=false;}
  });
  $("restoreExperience")?.addEventListener("click",async()=>{
    const scope=experienceScope(),version=Number($("experienceRevision").value),message=$("experienceMessage"),button=$("restoreExperience");
    if(!version){message.textContent="اختار إصدارًا منشورًا للاستعادة.";return;}
    if(!window.confirm("استعادة الإصدار "+version+" كمسودة؟"))return;
    button.disabled=true;message.textContent="جاري استعادة الإصدار...";
    try{
      await platformRequest("/api/platform/admin/experiences/restore",{method:"POST",body:JSON.stringify({...scope,version})});
      message.textContent="تمت استعادة الإصدار كمسودة. راجعه ثم انشره.";
      await loadExperienceStudio();
    }catch(error){message.textContent=error.message || "تعذرت استعادة الإصدار.";}
    finally{button.disabled=false;}
  });
  $("experienceSurface")?.addEventListener("change",loadExperienceStudio);
  $("experienceWorkspaceId")?.addEventListener("change",loadExperienceStudio);
  $("loadExperienceBtn")?.addEventListener("click",loadExperienceStudio);

  // Sidebar navigation: show one workspace section at a time.
  const pageLinks = Array.from(document.querySelectorAll("[data-page-link]"));
  const pages = Array.from(document.querySelectorAll("[data-page]"));
  function activatePage(pageName, updateHash = true) {
    const exists = pages.some((page) => page.dataset.page === pageName);
    const target = exists ? pageName : "overview";
    pages.forEach((page) => page.classList.toggle("active", page.dataset.page === target));
    pageLinks.forEach((link) => link.classList.toggle("active", link.dataset.pageLink === target));
    if (updateHash) {
      const activeLink = pageLinks.find((link) => link.dataset.pageLink === target);
      if (activeLink) history.replaceState(null, "", activeLink.getAttribute("href"));
    }
    if (target === "subscriptions" && token) { loadBillingPlans(); loadSubscriptionCustomers(); loadSubscriptions(); }
    if (target === "ai-team" && token) { loadAISettings(); loadPlatformTeam(); }
    if (target === "website" && token) { loadExperienceStudio(); }
    if (target === "operations" && token) { loadPlatformOperations(); }
    if (target === "ai-team" && token) { loadAISettings(); loadPlatformTeam(); }
    if (target === "customers" && token) {
      loadCustomers();
      loadTenantReadiness();
    }
  }
  pageLinks.forEach((link) => link.addEventListener("click", (event) => {
    event.preventDefault();
    activatePage(link.dataset.pageLink);
  }));
  const initialPage = pageLinks.find((link) => link.getAttribute("href") === location.hash)?.dataset.pageLink || "overview";
  activatePage(initialPage, false);

  // Accessible, responsive sidebar: collapsible rail on desktop and drawer on mobile.
  const sidebarToggle = $("sidebarToggle");
  const sidebarBackdrop = $("sidebarBackdrop");
  const isMobileSidebar = () => window.matchMedia("(max-width: 900px)").matches;
  function closeSidebar() {
    $("appView").classList.remove("sidebar-open");
    $("appView").classList.add("sidebar-collapsed");
    sidebarToggle?.setAttribute("aria-expanded", "false");
    sidebarToggle?.setAttribute("aria-label", "فتح القائمة الجانبية");
  }
  function openSidebar() {
    $("appView").classList.remove("sidebar-collapsed");
    if (isMobileSidebar()) $("appView").classList.add("sidebar-open");
    else $("appView").classList.remove("sidebar-open");
    sidebarToggle?.setAttribute("aria-expanded", "true");
    sidebarToggle?.setAttribute("aria-label", "إغلاق القائمة الجانبية");
  }
  sidebarToggle?.addEventListener("click", () => {
    const opened = isMobileSidebar()
      ? $("appView").classList.contains("sidebar-open")
      : !$("appView").classList.contains("sidebar-collapsed");
    if (opened) closeSidebar(); else openSidebar();
  });
  sidebarBackdrop?.addEventListener("click", closeSidebar);
  window.addEventListener("resize", () => {
    if (!isMobileSidebar()) openSidebar();
    else closeSidebar();
  });
  if (isMobileSidebar()) closeSidebar();
  else openSidebar();

  pageLinks.forEach((link) => link.addEventListener("click", () => { if (isMobileSidebar()) closeSidebar(); }));
  $("refreshBtn").addEventListener("click", loadOverview);
  // Restore the admin session after a page refresh in the same browser tab.
  if (token) {
    $("loginView").classList.add("hidden");
    $("appView").classList.remove("hidden");
    loadOverview();
    loadCustomers();
    loadTenantReadiness();
    if (initialPage === "website") loadExperienceStudio();
  }

  $("logoutBtn").addEventListener("click", () => {
    saveToken("");
    $("appView").classList.add("hidden");
    $("loginView").classList.remove("hidden");
    $("adminPass").value = "";
  });
})();