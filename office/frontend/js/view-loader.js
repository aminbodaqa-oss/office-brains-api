/* Loads independent interface fragments before initializing the shared Office runtime. */
(async function loadOfficeViews() {
  const mount = document.getElementById("officeViews");
  const status = document.getElementById("officeLoadStatus");
  if (!mount || !status) return;

  const viewFiles = [
    "views/login.html",
    "views/dashboard.html",
    "views/settings.html",
    "views/notifications.html",
    "views/employees.html",
    "views/meetings.html",
    "views/employee-chat.html"
  ];

  try {
    const fragments = await Promise.all(viewFiles.map(async (path) => {
      const response = await fetch(path, { cache: "no-cache" });
      if (!response.ok) throw new Error("تعذر تحميل الواجهة: " + path);
      return response.text();
    }));
    fragments.forEach((markup) => {
      const template = document.createElement("template");
      template.innerHTML = markup;
      mount.insertBefore(template.content, status);
    });

    for (const path of [
      "js/config.js",
      "js/branding.js",
      "js/app.js",
      "js/workspace.js",
      "js/whatsapp.js?v=1",
      "js/settings.js"
    ]) {
      await new Promise((resolve, reject) => {
        const script = document.createElement("script");
        script.src = path;
        script.onload = resolve;
        script.onerror = () => reject(new Error("تعذر تحميل ملف التشغيل: " + path));
        document.body.appendChild(script);
      });
    }
    status.hidden = true;
  } catch (error) {
    status.hidden = false;
    status.textContent = "تعذر تجهيز المكتب. حدّث الصفحة، وإذا استمرت المشكلة تواصل مع الدعم.";
    status.setAttribute("data-error", "true");
    console.error("Office Brains view loader:", error);
  }
})();
