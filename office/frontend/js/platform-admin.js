(() => {
  const API = "https://9ywu5lapwb.apps.bot-hosting.cloud";
  const $ = (id) => document.getElementById(id);
  let token = "";

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
      token = data.access_token;
      $("loginView").classList.add("hidden");
      $("appView").classList.remove("hidden");
      await loadOverview();
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
        token = "";
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

  $("refreshBtn").addEventListener("click", loadOverview);
  $("logoutBtn").addEventListener("click", () => {
    token = "";
    $("appView").classList.add("hidden");
    $("loginView").classList.remove("hidden");
    $("adminPass").value = "";
  });
})();