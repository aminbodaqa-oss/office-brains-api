(() => {
  const dock = document.getElementById("workspaceDock");
  if (!dock || document.getElementById("wsWhatsappBtn")) return;
  const style = document.createElement("style");
  style.textContent = "#wsWhatsappBtn:before{content:'';display:inline-block;width:8px;height:8px;margin-left:8px;border-radius:50%;background:#25a56a;vertical-align:middle}" +
    "#waWebPanel{display:none;margin-top:10px;border:1px solid var(--line);border-radius:16px;background:var(--card);overflow:hidden;box-shadow:0 8px 28px #0000000a}#waWebPanel.open{display:block}" +
    ".wa-web-head{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:14px 16px;border-bottom:1px solid var(--line)}.wa-web-head h2{margin:0;font-size:17px}.wa-web-head p{margin:2px 0 0;color:var(--mut);font-size:12px}" +
    ".wa-web-head button,.wa-web-contact,.wa-web-send button{font:inherit;cursor:pointer}.wa-web-head button{border:1px solid var(--line);background:var(--bg);color:var(--ink);border-radius:9px;padding:7px 11px}" +
    ".wa-web-layout{display:grid;grid-template-columns:minmax(220px,300px) minmax(0,1fr);min-height:480px}.wa-web-contacts{border-left:1px solid var(--line);overflow:auto;max-height:620px}" +
    ".wa-web-contact{display:flex;width:100%;align-items:center;gap:10px;text-align:right;padding:11px 13px;border:0;border-bottom:1px solid var(--line);background:transparent;color:var(--ink)}.wa-web-contact:hover,.wa-web-contact.active{background:var(--bg)}" +
    ".wa-web-avatar{width:40px;height:40px;flex:none;border-radius:50%;display:grid;place-items:center;background:#7047f51a;color:#7047f5;font-weight:800}.wa-web-contact-copy{min-width:0;flex:1}.wa-web-contact-copy b,.wa-web-contact-copy small{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.wa-web-contact-copy b{font-size:13px}.wa-web-contact-copy small{font-size:11px;color:var(--mut);direction:ltr;text-align:right}" +
    ".wa-web-conversation{display:flex;min-width:0;flex-direction:column;background:var(--bg)}.wa-web-thread-head{padding:12px 15px;border-bottom:1px solid var(--line);background:var(--card)}.wa-web-thread-head b{display:block;font-size:14px}.wa-web-thread-head small{color:var(--mut);font-size:11px}" +
    "#waWebMessages{display:flex;flex:1;flex-direction:column;gap:9px;overflow:auto;min-height:300px;max-height:490px;padding:15px}.wa-web-message{max-width:min(78%,560px);padding:9px 12px;border:1px solid var(--line);border-radius:14px;background:var(--card);white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px}.wa-web-message.mine{align-self:flex-start;background:var(--me);border-color:transparent}.wa-web-message.theirs{align-self:flex-end;background:var(--bot);border-color:transparent}.wa-web-message time{display:block;margin-top:5px;color:var(--mut);font-size:10px}" +
    ".wa-web-empty{display:grid;place-items:center;min-height:220px;padding:20px;text-align:center;color:var(--mut);font-size:13px}.wa-web-send{display:flex;gap:8px;padding:11px;border-top:1px solid var(--line);background:var(--card)}.wa-web-send textarea{min-width:0;min-height:42px;max-height:110px;resize:vertical;flex:1;border:1px solid var(--line);border-radius:11px;padding:9px 11px;background:var(--bg);color:var(--ink);font:inherit;font-size:13px}.wa-web-send button{border:0;border-radius:11px;padding:0 17px;background:#7047f5;color:#fff;font-weight:700}.wa-web-send button:disabled{opacity:.55;cursor:wait}.wa-web-status{padding:7px 12px;color:var(--mut);font-size:11px}" +
    "@media(max-width:650px){.wa-web-layout{grid-template-columns:1fr;min-height:0}.wa-web-contacts{display:flex;max-height:none;overflow-x:auto;border-left:0;border-bottom:1px solid var(--line)}.wa-web-contact{width:108px;min-width:108px;flex-direction:column;justify-content:center;gap:5px;border-bottom:0;border-left:1px solid var(--line);text-align:center;padding:9px 5px}.wa-web-contact-copy small{display:none}.wa-web-contact-copy b{max-width:98px;font-size:11px}#waWebMessages{min-height:260px;max-height:52vh}.wa-web-message{max-width:88%}}";
  document.head.append(style);
  const toolbar = dock.querySelector(".ws-toolbar");
  const button = document.createElement("button");
  button.id = "wsWhatsappBtn"; button.type = "button"; button.textContent = "واتساب المكتب";
  toolbar.append(button);
  const panel = document.createElement("section");
  panel.id = "waWebPanel";
  panel.innerHTML = '<div class="wa-web-head"><div><h2>WhatsApp Office</h2><p>محادثات داخلية بأرقام افتراضية خاصة بالمكتب</p></div><div style="display:flex;gap:7px"><button type="button" id="waWebRefresh">تحديث</button><button type="button" id="waWebClose">إغلاق</button></div></div>' +
    '<div class="wa-web-layout"><aside class="wa-web-contacts" id="waWebContacts"><div class="wa-web-empty">جاري تحميل الموظفين...</div></aside>' +
    '<section class="wa-web-conversation"><div class="wa-web-thread-head" id="waWebThreadHead"><b>اختار موظف لبدء المحادثة</b><small>رقم المالك الافتراضي: VO-000</small></div>' +
    '<div id="waWebMessages"><div class="wa-web-empty">اختار موظف من القائمة لعرض الرسائل.</div></div>' +
    '<form class="wa-web-send" id="waWebSendForm"><textarea id="waWebInput" rows="1" maxlength="6000" placeholder="اكتب رسالتك..." disabled></textarea><button id="waWebSend" type="submit" disabled>إرسال</button></form><div class="wa-web-status" id="waWebStatus">الرسائل محفوظة في قاعدة بيانات المكتب.</div></section></div>';
  dock.append(panel);
  const $ = id => document.getElementById(id);
  let contacts = [], selected = null, poll = null, loading = false;
  const authHeaders = json => {
    if (!window.ownerToken) throw new Error("سجّل الدخول إلى المكتب أولًا.");
    const headers = {Authorization:"Bearer " + window.ownerToken};
    if (json) headers["Content-Type"] = "application/json";
    return headers;
  };
  async function request(path, options) {
    const opts = options || {};
    const response = await fetch((window.OFFICE_API_URL || "").replace(/\/$/,"") + path,
      Object.assign({}, opts, {headers:authHeaders(!!opts.body)}));
    const data = await response.json().catch(() => ({}));
    if (response.status === 401) {
      window.ownerToken = null; sessionStorage.removeItem("office_owner_token");
      document.getElementById("authGate").classList.remove("hidden");
      throw new Error("انتهت جلسة الدخول. سجّل الدخول مرة أخرى.");
    }
    if (!response.ok) throw new Error(data.detail || "تعذر تنفيذ الطلب.");
    return data;
  }
  function status(message) { $("waWebStatus").textContent = message; }
  function renderContacts() {
    const host = $("waWebContacts"); host.textContent = "";
    contacts.forEach(person => {
      const item = document.createElement("button"); item.type = "button";
      item.className = "wa-web-contact" + (selected && selected.id === person.id ? " active" : "");
      const avatar = document.createElement("span"); avatar.className = "wa-web-avatar"; avatar.textContent = String(person.id || "?").slice(0,1);
      const copy = document.createElement("span"); copy.className = "wa-web-contact-copy";
      const name = document.createElement("b"); name.textContent = person.id;
      const number = document.createElement("small"); number.textContent = person.virtual_number || "رقم داخلي";
      copy.append(name, number); item.append(avatar, copy);
      item.addEventListener("click", () => selectContact(person)); host.append(item);
    });
  }
  async function loadContacts() {
    status("جاري تحميل جهات الاتصال...");
    try {
      const data = await request("/api/whatsapp/contacts"); contacts = data.contacts || [];
      renderContacts();
      if (selected) selected = contacts.find(item => item.id === selected.id) || null;
      if (!selected && contacts.length) await selectContact(contacts[0]);
      else if (selected) await loadThread();
      status("تم تحميل " + contacts.length + " جهة اتصال.");
    } catch (error) { $("waWebContacts").textContent = error.message; status(error.message); }
  }
  async function selectContact(person) {
    selected = person; renderContacts();
    $("waWebThreadHead").textContent = "";
    const name = document.createElement("b"); name.textContent = person.id;
    const meta = document.createElement("small"); meta.textContent = (person.role || person.department || "موظف") + " · " + (person.virtual_number || "");
    $("waWebThreadHead").append(name, meta);
    $("waWebInput").disabled = false; $("waWebSend").disabled = false;
    await loadThread();
  }
  function renderMessages(messages) {
    const box = $("waWebMessages");
    const wasNearBottom = box.scrollHeight - box.scrollTop - box.clientHeight < 90;
    box.textContent = "";
    if (!messages.length) {
      const empty = document.createElement("div"); empty.className = "wa-web-empty";
      empty.textContent = "مفيش رسائل بينك وبين الموظف ده لسه. ابعت أول رسالة."; box.append(empty); return;
    }
    messages.forEach(message => {
      const bubble = document.createElement("article");
      bubble.className = "wa-web-message " + (message.sender_id === "المالك" ? "mine" : "theirs");
      const body = document.createElement("div"); body.textContent = message.content || "";
      const time = document.createElement("time"); const date = new Date(message.created_at);
      time.textContent = Number.isNaN(date.getTime()) ? (message.created_at || "") : date.toLocaleString("ar-EG",{dateStyle:"short",timeStyle:"short"});
      bubble.append(body, time); box.append(bubble);
    });
    if (wasNearBottom) box.scrollTop = box.scrollHeight;
  }
  async function loadThread() {
    if (!selected || loading) return;
    loading = true;
    try {
      const query = "?employee_id=" + encodeURIComponent("المالك") + "&peer_id=" + encodeURIComponent(selected.id) + "&limit=150";
      const data = await request("/api/whatsapp/messages" + query);
      renderMessages(data.messages || []);
    } catch (error) { status(error.message); }
    finally { loading = false; }
  }
  $("waWebSendForm").addEventListener("submit", async event => {
    event.preventDefault();
    const content = $("waWebInput").value.trim(); if (!content || !selected) return;
    const send = $("waWebSend"); send.disabled = true;
    try {
      await request("/api/whatsapp/send", {method:"POST",body:JSON.stringify({sender_id:"المالك",recipient_id:selected.id,content})});
      $("waWebInput").value = ""; await loadThread(); status("تم إرسال الرسالة وحفظها.");
    } catch (error) { status(error.message); }
    finally { send.disabled = !selected; }
  });
  $("waWebInput").addEventListener("keydown", event => {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) { event.preventDefault(); $("waWebSendForm").requestSubmit(); }
  });
  button.addEventListener("click", async () => {
    panel.classList.add("open"); button.classList.add("primary");
    if (!contacts.length) await loadContacts();
    if (poll) clearInterval(poll);
    poll = setInterval(() => { if (panel.classList.contains("open")) loadThread(); }, 7000);
  });
  $("waWebClose").addEventListener("click", () => {
    panel.classList.remove("open"); button.classList.remove("primary");
    if (poll) { clearInterval(poll); poll = null; }
  });
  $("waWebRefresh").addEventListener("click", loadContacts);
  document.getElementById("logoutBtn").addEventListener("click", () => {
    if (poll) { clearInterval(poll); poll = null; }
    panel.classList.remove("open"); button.classList.remove("primary");
  });
})();