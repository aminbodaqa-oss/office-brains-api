(() => {
  const style = document.createElement("style");
  style.textContent = `
    #workspaceDock{max-width:1120px;margin:10px auto 18px;padding:0 16px}
    .ws-toolbar{display:flex;gap:8px;flex-wrap:wrap}
    .ws-toolbar button,.ws-panel button{border:1px solid var(--line);background:var(--card);color:var(--ink);border-radius:11px;padding:9px 13px;font:inherit;font-size:13px;cursor:pointer}
    .ws-toolbar button.primary,.ws-panel button.primary{background:var(--acc);border-color:var(--acc);color:var(--accink);font-weight:700}
    .ws-panel{display:none;margin-top:10px;padding:14px;background:var(--card);border:1px solid var(--line);border-radius:16px;box-shadow:0 8px 28px #0000000a}
    .ws-panel.open{display:block}
    .ws-head{display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap;margin-bottom:12px}
    .ws-head h2{margin:0;font-size:17px}
    .ws-muted{color:var(--mut);font-size:12px}
    .ws-stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:7px;margin:10px 0}
    .ws-stat{padding:10px;border:1px solid var(--line);border-radius:12px;background:var(--bg)}
    .ws-stat b{display:block;font-size:20px}
    .ws-stat span{font-size:11px;color:var(--mut)}
    .ws-task{padding:11px 0;border-top:1px solid var(--line);display:grid;grid-template-columns:minmax(0,1fr) auto;gap:8px}
    .ws-task strong{display:block;font-size:13px}
    .ws-task p{margin:3px 0;color:var(--mut);font-size:12px;white-space:pre-wrap}
    .ws-task small{color:var(--mut);font-size:11px}
    .ws-task select,.ws-form input,.ws-form textarea,.ws-form select{width:100%;min-width:0;border:1px solid var(--line);border-radius:10px;padding:9px;background:var(--bg);color:var(--ink);font:inherit;font-size:13px}
    .ws-form{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin:12px 0;padding:12px;background:var(--bg);border:1px solid var(--line);border-radius:13px}
    .ws-form label{display:block;font-size:11px;color:var(--mut);margin-bottom:4px}
    .ws-form .wide{grid-column:1/-1}
    .ws-form textarea{min-height:66px;resize:vertical}
    .ws-form button{grid-column:1/-1}
    .ws-row{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
    .ws-report{padding:13px;border:1px solid var(--line);border-radius:12px;background:var(--bg);white-space:pre-wrap;font-size:13px;line-height:1.9}
    .ws-execution{display:block;margin-top:5px;color:var(--mut);font-size:11px}
    .ws-result{margin-top:8px;padding:10px;border:1px solid var(--line);border-radius:10px;background:var(--bg)}
    .ws-result summary{cursor:pointer;font-size:12px;font-weight:700}
    .ws-result pre{white-space:pre-wrap;overflow-wrap:anywhere;font:inherit;font-size:12px;line-height:1.8;margin:8px 0 0}
    .ws-activity{padding:9px 0;border-bottom:1px solid var(--line);font-size:12px}
    .ws-activity:last-child{border-bottom:0}
    .ws-activity b{display:block}
    .ws-activity small{color:var(--mut)}
    .ws-empty{padding:18px;text-align:center;color:var(--mut);font-size:13px}
    @media(max-width:560px){.ws-stats{grid-template-columns:repeat(2,minmax(0,1fr))}.ws-form{grid-template-columns:1fr}.ws-form .wide,.ws-form button{grid-column:1}.ws-task{grid-template-columns:1fr}.ws-task>div:last-child{display:flex;gap:6px}.ws-task select{max-width:170px}}
  `;
  document.head.append(style);

  const dock = document.createElement("section");
  dock.id = "workspaceDock";
  dock.innerHTML = `
    <div class="ws-toolbar">
      <button class="primary" id="wsTasksBtn" type="button">📋 مهام الشركة</button>
      <button id="wsSalmaBtn" type="button">💬 اسألي سلمى</button>
      <button id="wsMeetingsBtn" type="button">🗓️ الاجتماعات</button>
      <button id="wsActivityBtn" type="button">🕘 سجل النشاط</button>
    </div>
    <section class="ws-panel" id="wsPanel">
      <div class="ws-head"><div><h2 id="wsTitle">مساحة إدارة العمل</h2><div class="ws-muted" id="wsSubtitle">بيانات محفوظة في قاعدة بيانات المكتب</div></div><div class="ws-row"><button id="wsRefresh" type="button">تحديث</button><button id="wsClose" type="button">إغلاق</button></div></div>
      <div id="wsContent"><div class="ws-empty">اختار قسم من الأعلى.</div></div>
    </section>`;
  const header = document.querySelector("header");
  if (header) header.insertAdjacentElement("afterend", dock);

  const $w = id => document.getElementById(id);
  let currentView = "tasks";
  let cachedOverview = null;
  const employeeOptions = () => (typeof T !== "undefined" ? T : []).map(e => `<option value="${e.n}">${e.n} — ${e.r}</option>`).join("");
  const esc = value => String(value ?? "").replace(/[&<>"']/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[ch]));
  const localDate = value => {
    if (!value) return "غير محدد";
    const d = new Date(value);
    return Number.isNaN(d.getTime()) ? value : d.toLocaleString("ar-EG",{dateStyle:"medium",timeStyle:"short"});
  };
  async function request(path, options = {}) {
    if (!ownerToken) throw new Error("سجّل الدخول أولًا.");
    const base = (window.OFFICE_API_URL || "").replace(/\/$/,"");
    const response = await fetch(base + path, {
      method: options.method || "GET",
      headers: { "Content-Type":"application/json", "Authorization":"Bearer " + ownerToken },
      body: options.body ? JSON.stringify(options.body) : undefined
    });
    const data = await response.json().catch(() => ({}));
    if (response.status === 401) {
      ownerToken = null;
      sessionStorage.removeItem(TOKEN_STORAGE_KEY);
      authGate.classList.remove("hidden");
      throw new Error("انتهت جلسة الدخول. سجّل الدخول مرة أخرى.");
    }
    if (!response.ok) throw new Error(data.detail || ("HTTP " + response.status));
    return data;
  }
  function show(view, title, subtitle) {
    currentView = view;
    $w("wsTitle").textContent = title;
    $w("wsSubtitle").textContent = subtitle || "بيانات محفوظة في قاعدة بيانات المكتب";
    $w("wsPanel").classList.add("open");
    render();
  }
  function renderError(error) {
    $w("wsContent").textContent = error && error.message ? error.message : "حصل خطأ غير متوقع.";
  }
  async function loadOverview() {
    const data = await request("/api/workspace/overview");
    cachedOverview = data;
    return data;
  }
  async function render() {
    $w("wsContent").innerHTML = '<div class="ws-empty">جاري تحميل البيانات...</div>';
    try {
      if (currentView === "tasks") return await renderTasks();
      if (currentView === "salma") return renderSalma();
      if (currentView === "meetings") return await renderMeetings();
      if (currentView === "activity") return await renderActivity();
    } catch (error) { renderError(error); }
  }
  async function renderTasks() {
    const data = await loadOverview();
    const counts = data.task_counts || {};
    const engine = data.task_execution_engine || {};
    const engineNotice = engine.ready
      ? '<div class="ws-muted" style="margin:8px 0;padding:10px;border:1px solid var(--line);border-radius:10px">محرك تنفيذ المهام مفعّل. النتائج تُسلّم للمراجعة ولا تُغلق تلقائيًا.</div>'
      : '<div class="ws-muted" style="margin:8px 0;padding:10px;border:1px solid var(--line);border-radius:10px">المهام ستُحفظ ويصل التكليف للموظف، لكن التنفيذ الآلي متوقف حاليًا. يلزم تفعيل AUTONOMOUS_OFFICE_ENABLED=true واختيار مزود ذكاء اصطناعي فعلي بدل demo على السيرفر.</div>';
    $w("wsContent").innerHTML = `
      ${engineNotice}
      <div class="ws-stats">
        <div class="ws-stat"><b>${data.tasks_total || 0}</b><span>كل المهام</span></div>
        <div class="ws-stat"><b>${counts.open || 0}</b><span>جديدة</span></div>
        <div class="ws-stat"><b>${counts.in_progress || 0}</b><span>قيد التنفيذ</span></div>
        <div class="ws-stat"><b>${data.overdue_tasks || 0}</b><span>متأخرة</span></div>
      </div>
      <form class="ws-form" id="wsTaskForm">
        <div class="wide"><label>عنوان المهمة</label><input name="title" required maxlength="180" placeholder="مثال: مراجعة أداء المسوقين"></div>
        <div class="wide"><label>تفاصيل المهمة</label><textarea name="description" maxlength="5000" placeholder="المطلوب والنتيجة المنتظرة..."></textarea></div>
        <div><label>الموظف المسؤول</label><select name="assigned_to" required><option value="">اختار الموظف</option>${employeeOptions()}</select></div>
        <div><label>الأولوية</label><select name="priority"><option value="normal">عادية</option><option value="high">عالية</option><option value="urgent">عاجلة</option><option value="low">منخفضة</option></select></div>
        <div class="wide"><label>الموعد النهائي (اختياري)</label><input name="due_at" type="datetime-local"></div>
        <button class="primary" type="submit">+ تسجيل المهمة وتكليف الموظف</button>
      </form>
      <div class="ws-head"><b>المهام المسجلة</b><span class="ws-muted">تغيير الحالة يُحفظ في قاعدة البيانات</span></div>
      <div id="wsTaskList"></div>`;
    const list = $w("wsTaskList");
    const tasks = data.tasks || [];
    if (!tasks.length) list.innerHTML = '<div class="ws-empty">لسه مفيش مهام مسجلة. ابدأ بأول تكليف.</div>';
    tasks.forEach(task => {
      const item = document.createElement("article");
      item.className = "ws-task";
      const details = document.createElement("div");
      const title = document.createElement("strong"); title.textContent = "#" + task.id + " · " + task.title;
      const desc = document.createElement("p"); desc.textContent = task.description || "بدون تفاصيل إضافية.";
      const meta = document.createElement("small"); meta.textContent = "المسؤول: " + task.assigned_to + " · الأولوية: " + task.priority + " · الموعد: " + localDate(task.due_at);
      const executionLabels = {queued:"في طابور التنفيذ",running:"الموظف بيجهز النتيجة",review:"نتيجة جاهزة للمراجعة",failed:"التنفيذ تعثر",completed:"معتمدة كمكتملة",cancelled:"ملغاة"};
      const execution = document.createElement("small"); execution.className = "ws-execution";
      execution.textContent = "حالة التنفيذ: " + (executionLabels[task.execution_status] || "لم يبدأ التنفيذ الآلي");
      details.append(title,desc,meta,execution);
      if (task.execution_result || task.execution_error) {
        const resultBox = document.createElement("details"); resultBox.className = "ws-result";
        const summary = document.createElement("summary"); summary.textContent = task.execution_error ? "تفاصيل تعثر التنفيذ" : "عرض نتيجة الموظف للمراجعة";
        const output = document.createElement("pre"); output.textContent = task.execution_error || task.execution_result;
        resultBox.append(summary,output); details.append(resultBox);
      }
      const actions = document.createElement("div");
      const select = document.createElement("select");
      select.innerHTML = '<option value="open">جديدة</option><option value="in_progress">قيد التنفيذ</option><option value="review">مراجعة</option><option value="completed">مكتملة</option><option value="cancelled">ملغاة</option>';
      select.value = task.status;
      const save = document.createElement("button"); save.type="button"; save.textContent="حفظ الحالة";
      save.addEventListener("click", async () => {
        save.disabled=true;
        try { await request("/api/tasks/" + task.id,{method:"PATCH",body:{status:select.value}}); await renderTasks(); }
        catch(error){ alert(error.message); save.disabled=false; }
      });
      actions.append(select,save);
      if (task.execution_status === "failed") {
        const retry = document.createElement("button"); retry.type = "button"; retry.textContent = "إعادة المحاولة";
        retry.addEventListener("click", async () => {
          retry.disabled = true;
          try { await request("/api/tasks/" + task.id + "/retry",{method:"POST"}); await renderTasks(); }
          catch(error){ alert(error.message); retry.disabled = false; }
        });
        actions.append(retry);
      }
      item.append(details,actions); list.append(item);
    });
    $w("wsTaskForm").addEventListener("submit", async event => {
      event.preventDefault();
      const form = event.currentTarget;
      const values = new FormData(form);
      const due = values.get("due_at");
      const button = form.querySelector("button[type=submit]"); button.disabled=true;
      try {
        await request("/api/tasks",{method:"POST",body:{
          title:String(values.get("title")||"").trim(),
          description:String(values.get("description")||""),
          assigned_to:String(values.get("assigned_to")||""),
          priority:String(values.get("priority")||"normal"),
          due_at:due ? new Date(due).toISOString() : null
        }});
        await renderTasks();
      } catch(error){ alert(error.message); button.disabled=false; }
    });
  }
  function renderSalma() {
    $w("wsContent").innerHTML = `
      <div class="ws-muted" style="margin-bottom:10px">سلمى تراجع المهام والاجتماعات والتقارير وسجل النشاط المحفوظ، وتفصل بين الواقع والاقتراحات. أي تكليف جديد يحتاج موافقتك.</div>
      <form class="ws-form" id="wsSalmaForm">
        <div class="wide"><label>عايز سلمى تساعدك في إيه؟</label><textarea class="wide" name="message" maxlength="6000" placeholder="نظمي لي يومي، إيه المتأخر؟ جهزي اجتماع مع الفريق، أو لخصي آخر التطورات...">نظمي لي يومي ووريني أهم المهام والمواعيد اللي محتاجة متابعة.</textarea></div>
        <button class="primary" type="submit">اسألي سلمى</button>
      </form>
      <div id="wsSalmaAnswer" class="ws-report">سلمى مستنياك يا ريس. قولّي نبدأ منين؟</div>`;
    $w("wsSalmaForm").addEventListener("submit", async event => {
      event.preventDefault();
      const form=event.currentTarget, button=form.querySelector("button");
      const answer=$w("wsSalmaAnswer"); button.disabled=true; answer.textContent="سلمى بتراجع بيانات المكتب وبتجهز لك الرد...";
      try {
        const result=await request("/api/secretary/briefing",{method:"POST",body:{message:String(new FormData(form).get("message")||"") }});
        answer.textContent=result.content || "سلمى لم ترسل ردًا.";
        if(typeof loadNotifications==="function")loadNotifications();
      } catch(error){answer.textContent=error.message;}
      finally{button.disabled=false;}
    });
  }
  async function renderMeetings() {
    const data=await request("/api/meetings?limit=50");
    $w("wsContent").innerHTML = `
      <form class="ws-form" id="wsMeetingForm">
        <div class="wide"><label>عنوان الاجتماع</label><input name="title" required maxlength="180" placeholder="اجتماع متابعة التسويق"></div>
        <div class="wide"><label>جدول الأعمال</label><textarea name="agenda" maxlength="5000" placeholder="النقاط المطلوب مناقشتها..."></textarea></div>
        <div><label>الموعد</label><input name="scheduled_at" type="datetime-local" required></div>
        <div><label>المشاركون (اختيار متعدد)</label><select name="attendees" multiple size="4" required>${employeeOptions()}</select></div>
        <button class="primary" type="submit">حفظ موعد الاجتماع</button>
      </form>
      <div class="ws-head"><b>الاجتماعات المسجلة</b></div><div id="wsMeetingList"></div>`;
    const list=$w("wsMeetingList");
    if(!(data.meetings||[]).length)list.innerHTML='<div class="ws-empty">لا توجد اجتماعات مجدولة حتى الآن.</div>';
    (data.meetings||[]).forEach(meeting=>{
      const item=document.createElement("article");item.className="ws-activity";
      const title=document.createElement("b");title.textContent=meeting.title+" · "+meeting.status;
      const info=document.createElement("div");info.textContent=localDate(meeting.scheduled_at)+" · الحضور: "+(meeting.attendees||[]).join("، ");
      const agenda=document.createElement("small");agenda.textContent=meeting.agenda||"بدون جدول أعمال";
      item.append(title,info,agenda);list.append(item);
    });
    $w("wsMeetingForm").addEventListener("submit",async event=>{
      event.preventDefault();const form=event.currentTarget,values=new FormData(form),button=form.querySelector("button");
      const selected=[...form.elements.attendees.selectedOptions].map(o=>o.value);
      button.disabled=true;
      try{
        await request("/api/meetings",{method:"POST",body:{
          title:String(values.get("title")||"").trim(),agenda:String(values.get("agenda")||""),
          attendees:selected,scheduled_at:new Date(String(values.get("scheduled_at"))).toISOString()
        }});
        await renderMeetings();
        if(typeof loadNotifications==="function")loadNotifications();
      }catch(error){alert(error.message);button.disabled=false;}
    });
  }
  async function renderActivity() {
    const data=await request("/api/activity?limit=80");
    $w("wsContent").innerHTML='<div id="wsActivityList"></div>';
    const list=$w("wsActivityList");
    if(!(data.activity||[]).length){list.innerHTML='<div class="ws-empty">سجل النشاط لسه فاضي. أي مهمة أو اجتماع هيتسجل هنا.</div>';return;}
    data.activity.forEach(entry=>{
      const item=document.createElement("article");item.className="ws-activity";
      const title=document.createElement("b");title.textContent=entry.summary;
      const info=document.createElement("small");info.textContent=entry.actor+" · "+entry.action+" · "+localDate(entry.created_at);
      item.append(title,info);
      if(entry.details){const detail=document.createElement("div");detail.textContent=entry.details;detail.style.whiteSpace="pre-wrap";detail.style.color="var(--mut)";detail.style.marginTop="4px";item.append(detail);}
      list.append(item);
    });
  }
  $w("wsTasksBtn").addEventListener("click",()=>show("tasks","مهام الشركة","تكليفات محفوظة، مسؤول واضح، وحالة قابلة للمتابعة."));
  $w("wsSalmaBtn").addEventListener("click",()=>show("salma","مكتب سلمى التنفيذي","مساعدتك الشخصية في تنظيم اليوم ومتابعة الشركة."));
  $w("wsMeetingsBtn").addEventListener("click",()=>show("meetings","جدول الاجتماعات","مواعيد وحضور وجدول أعمال محفوظة."));
  $w("wsActivityBtn").addEventListener("click",()=>show("activity","سجل نشاط المكتب","كل تغيير مسجل بفاعله ووقته."));
  $w("wsRefresh").addEventListener("click",render);
  $w("wsClose").addEventListener("click",()=>$w("wsPanel").classList.remove("open"));
  if (ownerToken) { /* the panel loads on demand after authentication */ }
})();