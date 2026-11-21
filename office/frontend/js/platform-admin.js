(() => {
  const API = "https://9ywu5lapwb.apps.bot-hosting.cloud";
  const $ = (id) => document.getElementById(id);
  let token = "";
  $("adminLogin").addEventListener("submit", async (event) => {
    event.preventDefault();
    $("loginError").textContent = "";
    const button = $("adminLogin").querySelector("button");
    button.disabled = true;
    try {
      const response = await fetch(API + "/api/platform/admin/login", {
        method: "POST", headers: {"Content-Type":"application/json"},
        body: JSON.stringify({username:$("adminUser").value.trim(),password:$("adminPass").value})
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "تعذر تسجيل الدخول.");
      token = data.access_token;
      $("loginView").classList.add("hidden");
      $("appView").classList.remove("hidden");
      await loadOverview();
    } catch (error) { $("loginError").textContent = error.message || "حدث خطأ غير متوقع."; }
    finally { button.disabled = false; }
  });
  async function loadOverview() {
    $("loadError").textContent = "";
    try {
      const response = await fetch(API + "/api/platform/admin/overview", {headers:{Authorization:"Bearer "+token}});
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "تعذر تحميل بيانات المنصة.");
      $("apiState").textContent = data.api.status === "ok" ? "متصل" : "غير متاح";
      $("provider").textContent = data.api.provider || "غير محدد";
      $("tasks").textContent = Number(data.operations.tasks_total || 0).toLocaleString("ar-EG");
      $("employees").textContent = Number(data.catalog.employee_templates || 0).toLocaleString("ar-EG");
    } catch (error) { $("loadError").textContent = error.message || "تعذر تحميل البيانات."; }
  }
  $("refreshBtn").addEventListener("click", loadOverview);
  $("logoutBtn").addEventListener("click", () => { token = ""; $("appView").classList.add("hidden"); $("loginView").classList.remove("hidden"); $("adminPass").value = ""; });
})();
