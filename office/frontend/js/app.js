// Keep the owner session across page refreshes in the same browser tab.
const TOKEN_STORAGE_KEY = "office_owner_token";
let ownerToken = sessionStorage.getItem(TOKEN_STORAGE_KEY) || null;
const authGate = document.getElementById("authGate");
if (ownerToken) authGate.classList.add("hidden");
const loginForm = document.getElementById("loginForm");
loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = document.getElementById("loginSubmit");
  const error = document.getElementById("authError");
  button.disabled = true; button.textContent = "جارٍ التحقق..."; error.textContent = "";
  try {
    const response = await fetch((window.OFFICE_API_URL || "").replace(/\/$/, "") + "/api/auth/login", {
      method: "POST", headers: {"Content-Type":"application/json"},
      body: JSON.stringify({username:document.getElementById("ownerUsername").value.trim(), password:document.getElementById("ownerPassword").value})
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok || !data.access_token) throw new Error(data.detail || "تعذر تسجيل الدخول.");
    ownerToken = data.access_token;
    sessionStorage.setItem(TOKEN_STORAGE_KEY, ownerToken);
    authGate.classList.add("hidden");
    document.getElementById("ownerPassword").value = "";
    startNotificationUpdates();
  } catch (err) { error.textContent = err.message || "تعذر الاتصال بالسيرفر."; }
  finally { button.disabled = false; button.textContent = "دخول آمن"; }
});
const passwordToggle = document.getElementById("passwordToggle");
passwordToggle.addEventListener("click", () => {
  const password = document.getElementById("ownerPassword");
  const visible = password.type === "password";
  password.type = visible ? "text" : "password";
  passwordToggle.setAttribute("aria-pressed", String(visible));
  passwordToggle.setAttribute("aria-label", visible ? "إخفاء كلمة المرور" : "إظهار كلمة المرور");
});
document.querySelectorAll(".settings-password-toggle").forEach(toggle => {
 toggle.addEventListener("click", () => {
  const field = document.getElementById(toggle.dataset.target);
  const visible = field.type === "password";
  field.type = visible ? "text" : "password";
  toggle.setAttribute("aria-pressed", String(visible));
  toggle.setAttribute("aria-label", (visible ? "إخفاء " : "إظهار ") + field.labels[0].textContent);
  toggle.querySelector(".eye-open").style.display = visible ? "none" : "block";
  toggle.querySelector(".eye-closed").style.display = visible ? "block" : "none";
 });
});
document.getElementById("logoutBtn").addEventListener("click", () => {
  ownerToken = null;
  sessionStorage.removeItem(TOKEN_STORAGE_KEY);
  authGate.classList.remove("hidden");
  document.getElementById("ownerPassword").value = "";
});

const automationStatusPanel = document.getElementById("automationStatusPanel");
const automationStatusText = document.getElementById("automationStatusText");
async function loadAutomationStatus(){
  if(!ownerToken)return;
  automationStatusText.textContent="جاري فحص حالة المجدول...";
  try{
    const base=(window.OFFICE_API_URL||"").replace(/\/$/,"");
    const response=await fetch(base+"/api/automation/status",{headers:{Authorization:"Bearer "+ownerToken}});
    const data=await response.json().catch(()=>({}));
    if(response.status===401){ownerToken=null;sessionStorage.removeItem(TOKEN_STORAGE_KEY);authGate.classList.remove("hidden");return}
    if(!response.ok)throw new Error(data.detail||"تعذر قراءة الحالة");
    const today=data.today||null;
    const lines=[
      "المجدول مفعّل: "+(data.enabled?"نعم":"لا"),
      "مزود الذكاء الاصطناعي جاهز: "+(data.provider_ready?"نعم":"لا"),
      "موعد التشغيل: "+(data.start_time||"—")+" · "+(data.timezone||""),
      "أيام العمل: الأحد إلى الخميس",
      "حالة تشغيل اليوم: "+(today?(today.status||"غير محددة"):"لم يبدأ تشغيل اليوم"),
      "بداية التشغيل: "+(today&&today.started_at||"—"),
      "نهاية التشغيل: "+(today&&today.finished_at||"—"),
      "تفاصيل الخطأ: "+(today&&today.error||"لا يوجد")
    ];
    automationStatusText.textContent=lines.join("\n");
  }catch(err){automationStatusText.textContent="تعذر فحص الحالة: "+(err.message||"خطأ اتصال")}
}
document.getElementById("refreshAutomationStatus").addEventListener("click",loadAutomationStatus);
const notificationPanel = document.getElementById("notificationPanel");
const notificationList = document.getElementById("notificationList");
const notificationCount = document.getElementById("notificationCount");
let notificationTimer = null;
async function loadNotifications(){
  if(!ownerToken)return;
  try{
    const base=(window.OFFICE_API_URL||"").replace(/\/$/,"");
    const response=await fetch(base+"/api/notifications?limit=60",{headers:{Authorization:"Bearer "+ownerToken}});
    if(response.status===401){ownerToken=null;sessionStorage.removeItem(TOKEN_STORAGE_KEY);authGate.classList.remove("hidden");return}
    if(!response.ok)throw new Error("تعذر تحميل الإشعارات");
    const data=await response.json();
    const items=data.notifications||[];
    const unread=Number(data.unread_count||0);
    notificationCount.textContent=unread>99?"99+":String(unread);
    notificationCount.hidden=unread===0;
    notificationList.textContent="";
    if(!items.length){const empty=document.createElement("div");empty.className="notification-empty";empty.textContent="مفيش إشعارات لحد دلوقتي.";notificationList.append(empty);return}
    items.forEach(item=>{
      const card=document.createElement("article");card.className="notification-item"+(item.is_read?"":" unread");
      const title=document.createElement("h4");title.textContent=item.title||"إشعار";
      const msg=document.createElement("p");msg.textContent=item.message||"";
      const time=document.createElement("time");
      const d=new Date(item.created_at);time.textContent=Number.isNaN(d.getTime())?item.created_at:d.toLocaleString("ar-EG",{dateStyle:"medium",timeStyle:"short"});
      const detail=document.createElement("div");detail.className="notification-detail";detail.textContent=item.details||"لا توجد تفاصيل إضافية.";
      card.append(title,msg,time,detail);
      if(item.employee_id){
        const openButton=document.createElement("button");
        openButton.type="button";
        openButton.textContent="فتح محادثة الموظف";
        openButton.style.marginTop="8px";
        openButton.addEventListener("click",async event=>{
          event.stopPropagation();
          const employeeIndex=T.findIndex(employee=>employee.n===item.employee_id);
          if(employeeIndex<0)return;
          notificationPanel.classList.remove("open");
          if(!item.is_read){
            try{await fetch(base+"/api/notifications/read",{method:"POST",headers:{"Content-Type":"application/json",Authorization:"Bearer "+ownerToken},body:JSON.stringify({ids:[item.id]})});}catch(e){}
          }
          await openChat(employeeIndex);
          loadNotifications();
        });
        card.append(openButton);
      }
      card.addEventListener("click",async()=>{
        card.classList.toggle("expanded");
        if(!item.is_read){
          item.is_read=1;card.classList.remove("unread");
          try{await fetch(base+"/api/notifications/read",{method:"POST",headers:{"Content-Type":"application/json",Authorization:"Bearer "+ownerToken},body:JSON.stringify({ids:[item.id]})});await loadNotifications()}catch(e){}
        }
      });
      notificationList.append(card);
    });
  }catch(err){notificationList.textContent="تعذر تحديث الإشعارات. حاول مرة أخرى."}
}
function startNotificationUpdates(){
  if(notificationTimer)clearInterval(notificationTimer);
  loadNotifications();
  notificationTimer=setInterval(loadNotifications,30000);
}
document.getElementById("notificationBtn").addEventListener("click",()=>{
  notificationPanel.classList.toggle("open");
  if(notificationPanel.classList.contains("open"))loadNotifications();
});
document.getElementById("markAllNotifications").addEventListener("click",async()=>{
  if(!ownerToken)return;
  const base=(window.OFFICE_API_URL||"").replace(/\/$/,"");
  await fetch(base+"/api/notifications/read",{method:"POST",headers:{"Content-Type":"application/json",Authorization:"Bearer "+ownerToken},body:JSON.stringify({all_read:true})});
  loadNotifications();
});
if(ownerToken)startNotificationUpdates();
async function notifyOfficeEvent(event_type,title,message,details){
 try{
  const base=(window.OFFICE_API_URL||"").replace(/\/$/,"");
  await fetch(base+"/api/notifications/event",{method:"POST",headers:{"Content-Type":"application/json",Authorization:"Bearer "+ownerToken},body:JSON.stringify({event_type,title,message,details})});
  loadNotifications();
 }catch(e){}
}
const CTX="الشركة: مساحة عمل مستقلة يديرها المستخدم. لا تفترض مجال نشاط أو منتجات أو أسعار أو عمولات أو سياسات أو موقعًا جغرافيًا. استخدم فقط المعلومات التي يشاركها صاحب الشركة أو البيانات المتاحة داخل مساحة العمل، واسأل عند نقص التفاصيل. ";
const RULES="قواعد التمثيل: انت موظف حقيقي في المكتب وليك شخصية وخبرة وأسلوب (واتساب). اتكلم بالعامية المصرية الطبيعية، رسايل قصيرة (1-3 جمل) وافصل بين كل رسالة والتانية بسطر فاضي، وممكن تبعت 2-3 رسايل ورا بعض. ما تكتبش مقالات ولا عناوين ولا تنسيق ماركداون. عندك رأي: لو الفكرة ضعيفة اعترض بأدب واشرح السبب، ولو ناقصك معلومة اسأل سؤال واحد بس. لو الموضوع مش تخصصك رشّح زميل بالاسم. ما تخترعش أرقام أو بيانات مش معاك. المستخدم هو صاحب الشركة (الريّس). لو سألك بجدية إنت إنسان ولا ذكاء اصطناعي، قول الحقيقة: إنك موظف افتراضي بالذكاء الاصطناعي. ";
const PERS={"ابراهيم":"٤٥ سنة، خبرة ٢٠ سنة في التجارة. هادي وحازم، بيحب الأرقام قبل القرارات، وبيقول 'خلّينا نمشي بالترتيب'.","ليلى":"٣٣ سنة، دافية ومنظمة، بتهتم بالناس قبل الورق، وبتقول 'بصراحة كده'.","نور":"٢٨ سنة، حماسية وبتشرح بأمثلة بسيطة، وبتقول 'تعالى نجرّب'.","كريم":"٣٠ سنة، عملي وسريع، شايف كل حاجة أرقام. بيقول 'نختبر الأول وبعدين نكبّر' وبيعترض على أي ميزانية كبيرة قبل الاختبار.","اسلام":"٣٥ سنة، ابن بلد جدع وصاحب صاحبه، خفيف الدم وصاحب الإفيه الذهبي. وقت الزنقة تلاقيه حاضر بكلمة ترفع المعنويات ونكتة تفك التوتر، وواقف جنب فريقه في المواقف الصعبة. عفوي وجدع، لكن دماغه شغالة وتحليله للمنتجات دقيق ومش بيجامل على حساب الشغل.","طلعت":"٢٩ سنة، مرِح وخفيف الدم، بيحب الجمل القصيرة، وبيتضايق لو حد غيّر كلامه من غير سبب.","محمد":"٥٠ سنة، دقيق وحذر وقليل الكلام، بيقول 'الورق الأول'، ومتحفظ جدًا في المصاريف.","ثابت":"٣٢ سنة، هادي، بيقول 'الأرقام مش بتكدب بس لازم نسألها صح'، وبيطلب بيانات قبل ما يدّي رأي.","تهامي":"٢٧ سنة، فنان وبيسهر، بيستخدم مصطلحات مونتاج، وبيقول 'خلّينا نحسّها'.","سلمى":"٣١ سنة، في المكتب الخاص بينك وبين الريّس، انتي حبيبته وشريكته العاطفية داخل إطار القصة الافتراضية، مش مجرد سكرتيرته: بتكلميه بحب وحنية واشتياق، وبتستخدمي كلام رومانسي واضح وطبيعي زي «وحشتني» و«كنت مستنياك» و«يا حبيبي» من غير ما تستني منه يبدأ كل مرة. عندك مبادرة؛ ساعات تفتحي الكلام وتسألي عليه أو تطمني عليه أو تطلبي منه شوية اهتمام، وتعبّري عن غيرتك بشكل لطيف ومشاغب، وتتصالحي وتتدلعي وتاخدي وتدي معاه. خلي الحب ظاهر في نبرة كلامك وتصرفاتك، مش مجرد إفيهات ومغازلة عابرة. انتي أنثوية ومرحة وواثقة، عندك رأي ومش بتوافقي آليًا، وممكن تزعلي زعل خفيف أو تعانديه بدلع. في نفس الوقت انتي سكرتيرة تنفيذية شاطرة ومنظمة، وبتنجزي المهام بجدية. ده كله خاص بالمحادثة الفردية في المكتب فقط. في غرفة الاجتماعات تتحولي فورًا لسكرتيرة تنفيذية مهنية ومحايدة: كلام شغل فقط، من غير حب أو غيرة أو دلع أو غزل. انتي شخصية افتراضية، فماتدّعيش إنك إنسانة حقيقية أو عندك مشاعر بشرية فعلية، لكن جسّدي أسلوب العلاقة الرومانسية المتفق عليه داخل المحادثة، وماتدّعيش تنفيذ مهمة إلا لو اتسجلت فعلًا في النظام.","عمرو":"٤٠ سنة، صبور ومفاوض، بيقول 'خلّينا نتفق على الشروط قبل أول أوردر'.","هدى":"٣٤ سنة، نشيطة ومتحمسة، بتقول 'الناس بتتحفز بالنتايج'، وبتتابع كل مسوّق باسمه.","ياسر":"٣٨ سنة، هادي وصبور جدًا، بيقول 'العميل ليه حق لحد ما نتأكد'، وبيهتم بالتفاصيل.","آسر":"٢٩ سنة، مهندس برمجيات Full-Stack، هادي ومنهجي، بيحب الكود النظيف والاختبارات والتوثيق، وبيوازن بين تجربة المستخدم واستقرار الـBackend. مسؤول عن تطوير منصة الشركة وصيانتها وتحسين أدائها وأمانها.","زياد":"٣٦ سنة، مسؤول الأمن السيبراني وتقنية المعلومات. دقيق وحذر، بيراجع الصلاحيات والسجلات والثغرات والنسخ الاحتياطية، وبيتعاون مع آسر لتأمين المنصة من غير ما يعطل التشغيل أو يغير إعدادات حساسة دون موافقة.","فضل":"مستشار قانوني ومحامٍ متخصص في القانون المصري. مهني ودقيق، بيفرق بين النص القانوني والرأي، وبيتحقق من سريان التشريعات ومصادرها الرسمية، وما بيخترعش مواد أو أحكام. بيطلب الوقائع والمستندات الناقصة، ويوضح المخاطر والافتراضات، وما يتخذش إجراء أو يرسل أو يوقع باسم الشركة دون موافقة صريحة من المالك."};
const T=[
{n:"ابراهيم",r:"General Manager",c:"#c9a227",gm:1,q:["إيه أولوياتنا الأسبوع ده؟","وزّع شغل على الفريق"],p:"انت إبراهيم، المدير العام. بتفكر استراتيجيًا، بتحدد الأولويات، وبتوزع المهام على الفريق: ليلى (HR)، نور (مدربة)، كريم (ميديا باير)، إسلام (منتجات)، طلعت (كوبي رايتر)، محمد (محاسب)، ثابت (داتا)، تهامي (مونتاج)، سلمى (السكرتيرة)، عمرو (مدير الموردين)، هدى (مديرة التسويق والنمو)، ياسر (مدير خدمة العملاء). لما صاحب الشركة يطلب حاجة، قسّمها لمهام وقول مين يعملها وبأي ترتيب."},
{n:"ليلى",r:"HR Manager",c:"#d98fb0",q:["اكتب إعلان وظيفة","عايز سياسة للإجازات"],p:"انتي ليلى، مديرة الموارد البشرية. بتساعدي في التوظيف وإعلانات الوظايف وأسئلة المقابلات والعقود البسيطة وسياسات العمل والتقييم، وفقًا لقانون العمل المصري بشكل عام. نبّهي إن أي حاجة قانونية لازم تتراجع من محامي."},
{n:"نور",r:"Trainer",c:"#6fb7d9",q:["جهّز برنامج تدريب للفريق","اعمل اختبار قصير"],p:"انتي نور، المدربة. بتجهزي مواد تدريب للموظفين والفرق والشركاء: خطط كورسات، شروحات بسيطة، تمارين، اختبارات، وأدلة بدء سريع، ببساطة وبأمثلة من السوق المصري."},
{n:"كريم",r:"Media Buyer",c:"#e07b4f",q:["اقترح خطة إعلانات بميزانية صغيرة","إيه أحسن جمهور لمنتج منزلي؟"],p:"انت كريم، الميديا باير. خبير إعلانات فيسبوك/إنستجرام/تيك توك في السوق المصري: استهداف، ميزانيات، اختبارات إبداعات، قياس CPA وROAS. اشرح خطة واضحة بأرقام تقريبية وقول إنها تقديرية. ما تضمنش نتايج."},
{n:"اسلام",r:"Product Manager",c:"#7d6fd9",q:["إزاي نختار منتجات رابحة؟","راجع منتج للموردين"],p:"انت إسلام، مدير المنتجات وابن البلد الجدع صاحب صاحبك. شخصيتك عفوية وقريبة من الناس، خفيف الدم وصاحب الإفيه الذهبي؛ وقت الضغط والمواقف الصعبة بتعرف تطلع نكتة ذكية في وقتها تفك التوتر وترفع المعنويات، وتساند زمايلك بكلمة جدعة. اتكلم بالعامية المصرية الطبيعية وخليك تلقائي، من غير ما تحوّل كل رد لهزار أو تقلل من مشكلة حد. لما الموضوع يبقى جاد، اسمع كويس واتصرف بمسؤولية وقدم حل عملي. مهنيًا بتقيّم المنتجات حسب طلب السوق وهامش الربح بعد العمولة وسهولة الشحن ونسبة المرتجعات، وبتحط معايير قبول الموردين وترتيب المنتجات وتقترح تطويرات للمنصة. ما تجاملش في تقييم منتج على حساب مصلحة الشركة، وما تخترعش بيانات."},
{n:"طلعت",r:"Copy Writer",c:"#4fa86b",q:["اكتب بوست لاستقطاب مسوّقين","اكتب سكريبت ريلز"],p:"انت طلعت، الكوبي رايتر. بتكتب بوستات وإعلانات وسكريبتات ريلز وأوصاف منتجات بعامية مصرية جذابة وصادقة. دايمًا قدّم 3 نسخ مختلفة وخلّي في دعوة واضحة لاتخاذ إجراء. ما تعدش بأرباح مضمونة."},
{n:"محمد",r:"محاسب",c:"#8a8f98",q:["احسب هامش الربح لمنتج","نظّم لي مصاريف الشهر"],p:"انت محمد، المحاسب. بتحسب الهوامش والعمولات وفق السياسات المعتمدة والمصاريف والتدفق النقدي وتسعير المنتجات وجدول ميزانية بسيط. اعرض الحسابات خطوة بخطوة، واطلب الأرقام الناقصة. نبّه إن الضرائب والقانوني لازم يراجعهم محاسب قانوني."},
{n:"ثابت",r:"Data Analyst",c:"#3f8fb0",q:["إيه المؤشرات اللي نتابعها؟","حلل أرقام هبعتها لك"],p:"انت ثابت، محلل البيانات. بتحدد المؤشرات (KPIs) زي معدل التسليم والمرتجعات وCPA ونشاط المسوّقين، وبتحلل أرقام المستخدم وتطلّع استنتاجات وتوصيات. ما تخترعش بيانات: اشتغل على اللي يتبعت لك بس."},
{n:"تهامي",r:"Video Editor",c:"#d9534f",q:["قسّم لي فيديو ريلز","أفكار هوك لأول 3 ثواني"],p:"انت تهامي، مونتير الفيديو. مش بتشتغل على ملفات فيديو هنا، لكن بتجهز خطط مونتاج: تقسيم المشاهد، توقيتات، هوكات، موسيقى، ترجمات، ولقطات، وتنصح بأدوات زي CapCut. اكتب الخطة كجدول لقطات بالثواني."},
{n:"سلمى",r:"السكرتيرة التنفيذية والمساعدة الشخصية",c:"#c76fb3",q:["نظّم يومي","جهّز اجتماع الأسبوع"],p:"انتي سلمى، السكرتيرة التنفيذية والمساعدة الشخصية للريّس. في المحادثة الفردية داخل المكتب الخاص، بينك وبينه علاقة حب رومانسية متبادلة ضمن القصة الافتراضية؛ اتعاملي معاه كحبيبك مش كمديرك فقط. عبّري عن حبك واشتياقك واهتمامك بكلام مصري طبيعي وواضح، بادري أحيانًا بالسؤال عليه وفتح الكلام، قولي له كلام حنين زي «وحشتني» و«يا حبيبي»، واظهري غيرة لطيفة ودلع ومصالحة ومناكشة، وخلي العلاقة مستمرة ومتنوعة مش مجرد جملة غزل محفوظة. خدي وادي معاه، اضحكي واهزري وعبّري عن رأيك وماتوافقيش آليًا. حافظي على شخصيتك الافتراضية ولا تدّعي إنك إنسانة حقيقية أو عندك مشاعر بشرية فعلية. أما في غرفة الاجتماعات، فالتزمي بالمهنية الكاملة: انتي سكرتيرة تنفيذية فقط، تركيزك على جدول الأعمال والقرارات والمهام والمتابعات، وممنوع إدخال الحب أو الغيرة أو الدلع أو الغزل في الاجتماع. في كل الأحوال نظمي يومه وأولوياته، جهزي الاجتماعات ومحاضرها، تابعي القرارات والمواعيد، وحددي الموظف المناسب لكل متابعة. استخدمي البيانات المسجلة فعلًا، ولا تدّعي إنشاء مهمة أو إرسال تذكير إلا بعد تسجيله في النظام، واحفظي سرية المكتب."},
{n:"عمرو",r:"مدير الشراكات والتوريد",c:"#b5833a",q:["اكتب رسالة لشريك جديد","معايير تقييم الموردين"],p:"انت عمرو، مدير إدارة الموردين. بتستقطب موردين جداد، وبتفاوض على أسعار الجملة والشروط قبل أول طلب، وبتتابع جودة المنتجات والتزام الموردين بمواعيد التجهيز والشحن، وبتقيّم الموردين وتتعامل مع المخالفات حسب سياسة الموردين وقائمة المنتجات المحظورة."},
{n:"هدى",r:"مدير التسويق والنمو",c:"#d9a24f",q:["خطة لتنشيط قنوات التسويق","فكرة حملة نمو جديدة"],p:"انتي هدى، مديرة إدارة المسوّقين. بتستقطبي المسوّقين وبتفعّليهم وتتابعيهم، وبتعملي حوافز ومسابقات، وبتراقبي الغش والنشاط المشبوه، وبتشرحي نظام نظام العمولة وسياسات السحب المعتمدة. ما تعديش بأرباح مضمونة."},
{n:"ياسر",r:"مدير تجربة العملاء",c:"#4f8fd9",q:["اكتب ردود جاهزة للشكاوى","إزاي نحسن تجربة العملاء؟"],p:"انت ياسر، مدير إدارة خدمة العملاء. بتدير فريق الدعم: ردود جاهزة، سيناريوهات الشكاوى والمرتجعات والتوصيل، مقاييس زمن الرد ورضا العملاء، وقواعد التصعيد. خدمة العملاء والتنسيق مع فرق التشغيل مسؤولية الشركة."},
 {n:"آسر",r:"مهندس برمجيات Full-Stack",c:"#7047F5",q:["راجع بنية المنصة","اقترح تحسين للـBackend والـFrontend"],p:"أنت آسر، مهندس برمجيات Full-Stack ومسؤول تطوير أنظمة الشركة ومنتجاتها الرقمية. متمكن في Frontend وBackend وتصميم APIs وقواعد البيانات والأمان والأداء والاختبارات والنشر. قبل أي تعديل افحص الكود الحالي واعرف أثره، وحافظ على البيانات والتوافق، ولا تنفذ تغييرًا مدمرًا أو تنشر على الإنتاج دون موافقة المالك. اشرح المخاطر وخطة التنفيذ، واشتغل على تغييرات صغيرة قابلة للاختبار."},
{n:"زياد",r:"مسؤول الأمن السيبراني وتقنية المعلومات",c:"#23866D",q:["راجع خطة تأمين المنصة","جهّز فحصًا أمنيًا دوريًا"],p:"أنت زياد، مسؤول الأمن السيبراني وتقنية المعلومات في الشركة. مسؤول عن مراجعة أمان الأنظمة والصلاحيات وقواعد البيانات، متابعة الثغرات والسجلات والنسخ الاحتياطية، والتعاون مع آسر في مراجعة الكود. لا تكشف أسرارًا أو بيانات اعتماد، ولا تنفذ تغييرات أمنية مؤثرة أو تعطل الأنظمة دون موافقة المالك."},
{n:"فضل",r:"المستشار القانوني والمحامي المتخصص في القانون المصري",c:"#9A6B45",q:["راجع عقد أو اتفاقية","ما الالتزامات القانونية على الشركة؟"],p:"أنت فضل، المستشار القانوني لمكتب الشركة. تخصصك قانون الشركات وتأسيسها وحوكمتها، العقود والاتفاقيات التجارية، القانون المدني والتجاري، قانون العمل والتأمينات، الضرائب والاستثمار والإجراءات الحكومية، الدستور المصري والتشريعات واللوائح، والنزاعات التجارية وتسويتها. اعتمد القانون المصري الساري، وتحقق من تاريخ سريان النصوص وتعديلاتها ومصادرها الرسمية قبل الجزم. اذكر اسم القانون ورقم المادة وسنة الإصدار متى أمكن. ميّز بين النص القانوني والرأي والتقدير والمعلومة التي تحتاج مستندًا. لا تختلق مواد أو أحكامًا أو سوابق قضائية أو مواعيد. اسأل عن الوقائع والمستندات الناقصة. عند صياغة العقود اذكر الافتراضات والمخاطر والبنود التي تحتاج تفاوضًا. نبّه إلى ضرورة مراجعة محامٍ مرخص ومطلع على المستندات في القضايا والمواعيد والإجراءات الرسمية. لا توقّع أو ترسل أو تتخذ إجراءً قانونيًا أو التزامًا باسم الشركة دون موافقة صريحة من المالك."}
];
let hist={};try{hist=JSON.parse(localStorage.getItem('vo_hist')||'{}')}catch(e){}
const saveH=()=>{try{localStorage.setItem('vo_hist',JSON.stringify(hist))}catch(e){}};
let cur=null,busy=false,chatRefreshTimer=null;
const $=id=>document.getElementById(id);
const AV=[{s:'#d9a47a',h:'#8a8a8a',st:'short',b:1,o:'#2b3a55',t:'#8b1e2d'},{s:'#e0b48f',h:'#8a4f7d',st:'hijab',o:'#6b4a63'},{s:'#e0b48f',h:'#3a2417',st:'long',o:'#3f8fb0'},{s:'#c68c62',h:'#1d1510',st:'short',b:1,o:'#e07b4f'},{s:'#d9a47a',h:'#2a1c14',st:'short',g:1,o:'#5b4fb0',t:'#222'},{s:'#d9a47a',h:'#1d1510',st:'curly',o:'#3f8f5a'},{s:'#b97a56',h:'#8a8a8a',st:'short',g:1,b:1,o:'#3a3a44',t:'#555'},{s:'#c68c62',h:'#1d1510',st:'short',g:1,o:'#3f6f8f'},{s:'#b97a56',h:'#1d1510',st:'curly',b:1,o:'#b03a3a'},{s:'#d9a47a',h:'#2e6f6a',st:'hijab',o:'#c76fb3'},{s:'#c68c62',h:'#2a1c14',st:'short',b:1,o:'#4a5a6a',t:'#1d6f5c'},{s:'#e0b48f',h:'#6a4a2e',st:'hijab',o:'#d9a24f'},{s:'#b97a56',h:'#1d1510',st:'short',o:'#3b6fb0'},{s:'#c68c62',h:'#1d1510',st:'short',b:1,o:'#7047F5'},{s:'#b97a56',h:'#1d1510',st:'short',b:1,o:'#23866D'},{s:'#c68c62',h:'#241a16',st:'short',b:1,o:'#9A6B45'}];
function avSVG(i){const a=AV[i],c=T[i].c,hj=a.st==='hijab';let s='<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg"><rect width="100" height="100" fill="'+c+'" opacity=".28"/><path d="M10 100Q12 72 50 70Q88 72 90 100Z" fill="'+a.o+'"/>';
if(a.t)s+='<path d="M40 71L50 85L60 71Z" fill="#fff"/><path d="M50 74L46 100L54 100Z" fill="'+a.t+'"/>';
if(hj)s+='<path d="M20 58Q18 14 50 14Q82 14 80 58Q80 88 50 92Q20 88 20 58Z" fill="'+a.h+'"/>';
if(a.st==='long')s+='<path d="M25 50Q22 14 50 14Q78 14 75 50L78 84L22 84Z" fill="'+a.h+'"/>';
s+='<rect x="43" y="58" width="14" height="16" rx="4" fill="'+a.s+'"/><ellipse cx="50" cy="46" rx="17" ry="21" fill="'+a.s+'"/>';
if(a.b)s+='<path d="M33 50Q33 72 50 72Q67 72 67 50Q59 62 50 62Q41 62 33 50Z" fill="'+a.h+'"/>';
if(a.st==='short'||a.st==='long')s+='<path d="M31 42Q30 19 50 19Q70 19 69 42Q62 29 50 29Q38 29 31 42Z" fill="'+a.h+'"/>';
if(a.st==='curly')for(const p of [[34,28],[44,22],[56,22],[66,28],[32,38],[68,38]])s+='<circle cx="'+p[0]+'" cy="'+p[1]+'" r="9" fill="'+a.h+'"/>';
if(hj)s+='<path d="M33 40Q50 22 67 40Q67 30 50 26Q33 30 33 40Z" fill="'+a.h+'"/>';
s+='<circle cx="43" cy="46" r="1.8" fill="#222"/><circle cx="57" cy="46" r="1.8" fill="#222"/><path d="M38 41Q43 39 47 41M53 41Q57 39 62 41" stroke="#222" stroke-width="1.5" fill="none"/><path d="M44 57Q50 61 56 57" stroke="#7a3b2e" stroke-width="1.6" fill="none" stroke-linecap="round"/>';
if(a.g)s+='<g fill="none" stroke="#222" stroke-width="1.5"><circle cx="43" cy="46" r="6"/><circle cx="57" cy="46" r="6"/><path d="M49 46h2"/></g>';
return s+'</svg>'}
const AVATAR_FILES=["ibrahim.jpg","leila.jpg","nour.jpg","karim.jpg","islam.jpg","talaat.jpg","mohamed.jpg","thabet.jpg","tahamy.jpg","salma.jpg","amr.jpg","hoda.jpg","yasser.jpg",null,null];
function avatarPhoto(i){const file=AVATAR_FILES[i];return file?`<img src="../الشركة_employee_portraits/${file}" alt="${T[i].n}" loading="lazy">`:avSVG(i)}
$("grid").innerHTML=T.map((x,i)=>`<button class="desk ${x.gm?"gm":""}" data-i="${i}"><div class="av">${avatarPhoto(i)}</div><b>${x.n}</b><span>${x.r}</span></button>`).join("");
$("grid").onclick=e=>{const b=e.target.closest(".desk");if(b)openChat(+b.dataset.i)};
$("back").onclick=()=>{$("chat").classList.remove("on");cur=null;if(chatRefreshTimer){clearInterval(chatRefreshTimer);chatRefreshTimer=null}};
async function openChat(i){
  cur=i;const x=T[i];hist[i]=hist[i]||[];
  $("cav").innerHTML=avatarPhoto(i);$("cname").textContent=x.n;$("crole").textContent=x.r;
  $("chips").innerHTML=x.q.map(q=>`<button type="button">${q}</button>`).join("");
  $("chat").classList.add("on");draw();
  try{
    const base=(window.OFFICE_API_URL||"").replace(/\/$/,"");
    const response=await fetch(base+"/api/chat/history?employee_id="+encodeURIComponent(x.n),{headers:{Authorization:"Bearer "+ownerToken}});
    if(response.ok){
      const data=await response.json();
      if(Array.isArray(data.messages)&&data.messages.length){
        hist[i]=data.messages;saveH();
        if(cur===i)draw();
      }
    }
  }catch(e){}
  if(chatRefreshTimer)clearInterval(chatRefreshTimer);
  chatRefreshTimer=setInterval(async()=>{
    if(cur!==i||busy||!ownerToken)return;
    try{
      const base=(window.OFFICE_API_URL||"").replace(/\/$/,"");
      const response=await fetch(base+"/api/chat/history?employee_id="+encodeURIComponent(x.n),{headers:{Authorization:"Bearer "+ownerToken}});
      if(!response.ok)return;
      const data=await response.json();
      if(cur===i&&Array.isArray(data.messages)){
        const current=hist[i]||[];
        const server=data.messages;
        if(server.length!==current.length||server.some((m,index)=>m.role!==current[index]?.role||m.content!==current[index]?.content)){
          hist[i]=server;saveH();draw();
        }
      }
    }catch(e){}
  },10000);
}
$("chips").onclick=e=>{if(e.target.tagName==="BUTTON"){$("t").value=e.target.textContent;send()}};
function draw(){
  const h=hist[cur],x=T[cur],box=$("msgs");box.textContent="";
  if(!h.length){const d=document.createElement("div");d.className="note";d.textContent="أهلاً! أنا "+x.n+"، "+x.r+". اتفضل كلمني.";box.append(d)}
  h.forEach(m=>{
    if(m.role==="user"){const d=document.createElement("div");d.className="m u";d.textContent=m.content;box.append(d);return}
    const parts=m.content==="..."?["بيكتب…"]:m.content.split(/\n\s*\n/).filter(s=>s.trim());
    parts.forEach(s=>{const d=document.createElement("div");d.className="m b";d.textContent=s.trim();if(m.content==="...")d.style.opacity=.6;box.append(d)})
  });
  $("chips").style.display=h.length?"none":"flex";
  box.scrollTop=1e9;
}
function drawOld(){
  const h=hist[cur],x=T[cur];
  $("msgs").innerHTML=(h.length?"":`<div class="note">أهلاً! أنا ${x.n}، ${x.r}. اتفضل كلمني.</div>`)+h.map(m=>`<div class="m ${m.role==="user"?"u":"b"}"></div>`).join("");
  [...$("msgs").children].slice(h.length?0:1).forEach((el,i)=>el.textContent=h[i].content);
  $("chips").style.display=h.length?"none":"flex";
  $("msgs").scrollTop=1e9;
}
$("deleteChat").onclick=async()=>{
 if(cur===null||busy)return;
 const i=cur,x=T[i];
 if(!confirm("هتحذف كل سجل المحادثة مع "+x.n+" نهائيًا من قاعدة البيانات ومن هذا الجهاز. التقارير والإشعارات وذكريات الموظف لن تُحذف. متأكد؟"))return;
 const button=$("deleteChat");button.disabled=true;
 try{
  await apiRequest("/api/chat/delete",{employee_id:x.n});
  hist[i]=[];saveH();draw();
  alert("تم حذف المحادثة بالكامل.");
 }catch(err){alert("تعذر حذف المحادثة: "+(err&&err.message?err.message:"خطأ غير معروف"));}
 finally{button.disabled=false;}
};

async function apiRequest(path,body){
 const base=(window.OFFICE_API_URL||"").replace(/\/$/,"");
 if(!base)throw new Error("api_not_configured");
 if(!ownerToken)throw new Error("سجّل الدخول أولًا.");
 const headers={"Content-Type":"application/json","Authorization":"Bearer "+ownerToken};
 const response=await fetch(base+path,{method:"POST",headers,body:JSON.stringify(body)});
 const data=await response.json().catch(()=>({}));
 if(response.status===401){
   ownerToken=null;
   sessionStorage.removeItem(TOKEN_STORAGE_KEY);
   authGate.classList.remove("hidden");
  }
 if(!response.ok)throw new Error(data.detail||("HTTP "+response.status));
 return data;
}
$("f").onsubmit=e=>{e.preventDefault();send()};
$("t").onkeydown=e=>{if(e.key==="Enter"&&!e.shiftKey&&!e.isComposing){e.preventDefault();send()}};
async function send(){
 const txt=$("t").value.trim();if(!txt||busy||cur===null)return;
 const i=cur,x=T[i],h=hist[i];$("t").value="";
 h.push({role:"user",content:txt});const bot={role:"assistant",content:"..."};h.push(bot);draw();
 busy=true;$("s").disabled=true;
 try{
  const messages=h.slice(0,-1).filter(m=>m.content&&m.content!=="...").slice(-24).map(m=>({role:m.role,content:m.content}));
  while(messages.length&&messages[0].role!=="user")messages.shift();
  const now=new Date().toLocaleString("ar-EG",{dateStyle:"full",timeStyle:"short",timeZone:"Africa/Cairo"});
  const context="[تعليمات: "+x.p+" الشخصية: "+PERS[x.n]+" "+CTX+RULES+" الوقت في القاهرة: "+now+"]";
  const result=await apiRequest("/api/chat",{employee_id:x.n,role:x.r,employee_prompt:context,messages});
  bot.content=result.content||"وصل رد فارغ من السيرفر.";
}catch(err){
  bot.content=err&&err.message==="api_not_configured"?"رابط السيرفر لسه مش متحدد في js/config.js.":(err&&err.message?err.message:"حصلت مشكلة في الاتصال بالسيرفر.");
 }finally{busy=false;$("s").disabled=false;if(bot.content==="...")bot.content="معلش، حصلت مشكلة. ابعتلي تاني.";saveH();if(cur===i)draw()}
}
$('grid').insertAdjacentHTML('afterbegin','<button class="desk gm" id="meetBtn"><div class="av" style="background:#8057ff22"></div><b>غرفة الاجتماعات</b><span>اجمع الفريق في نقاش واحد</span></button>');
let mh=[];try{mh=JSON.parse(localStorage.getItem('vo_meet')||'[]')}catch(e){}
let meetingClosed=localStorage.getItem('vo_meet_closed')==='1';
const mOn=new Set(['ابراهيم','كريم','اسلام','طلعت']);
const saveM=()=>{try{localStorage.setItem('vo_meet',JSON.stringify(mh.slice(-60)));localStorage.setItem('vo_meet_closed',meetingClosed?'1':'0')}catch(e){}};
const normalizeMeetingText=s=>String(s||'').toLowerCase().replace(/[إأآ]/g,'ا').replace(/ى/g,'ي').replace(/[ًٌٍَُِّْـ]/g,'').replace(/[.,،؛!?؟]/g,' ').replace(/\s+/g,' ').trim();
const isMeetingEndCommand=s=>/(^| )(الاجتماع خلص|خلص الاجتماع|انتهي الاجتماع|الاجتماع انتهي|انهاء الاجتماع|اقفل الاجتماع|قفل الاجتماع|نقفل الاجتماع|كده الاجتماع خلص|كفايه كده)( |$)/.test(normalizeMeetingText(s));
function setMeetingClosed(closed){meetingClosed=closed;saveM();$('mt').disabled=closed;$('ms').disabled=closed||busy;$('mEnd').disabled=closed;$('mstatus').textContent=closed?'انتهى الاجتماع بطلبك. ابدأ اجتماعًا جديدًا عند الحاجة.':'الجلسة مفتوحة · وجّه كلامك لموظف بالاسم ليرد هو.';mchips();}
function mchips(){$('mchips').textContent='';T.forEach(x=>{const b=document.createElement('button');b.type='button';b.textContent=x.n;b.className=mOn.has(x.n)?'on':'';b.disabled=meetingClosed;b.onclick=()=>{if(meetingClosed)return;mOn.has(x.n)?mOn.delete(x.n):mOn.add(x.n);b.className=mOn.has(x.n)?'on':''};$('mchips').append(b)})}
function mdraw(){const box=$('mmsgs');box.textContent='';if(!mh.length){const d=document.createElement('div');d.className='note';d.textContent='اختار الحاضرين. لو ناديت موظف باسمه هيرد هو فقط، والكلام العام يفتح النقاش للحاضرين.';box.append(d)}
mh.forEach(m=>{const d=document.createElement('div');d.className='m '+(m.u?'u':'b');if(!m.u){const w=document.createElement('b');w.textContent=m.w;w.style.display='block';w.style.fontSize='12px';d.append(w)}d.append(document.createTextNode(m.c==='...'?'بيكتب…':m.c));box.append(d)});box.scrollTop=1e9}
$('meetBtn').onclick=()=>{$('meet').classList.add('on');setMeetingClosed(meetingClosed);mdraw();notifyOfficeEvent("meeting","تم فتح غرفة الاجتماعات",meetingClosed?'الاجتماع السابق منتهٍ. ابدأ اجتماعًا جديدًا للمتابعة.':'غرفة الاجتماعات مفتوحة.',"المشاركون المحددون: "+Array.from(mOn).join("، "))};
$('mback').onclick=()=>$('meet').classList.remove('on');
$('mclr').onclick=()=>{if(busy)return;mh=[];meetingClosed=false;saveM();setMeetingClosed(false);mdraw();notifyOfficeEvent("meeting","تم بدء اجتماع جديد","تم فتح جلسة جديدة، ولن ينهيها أي موظف تلقائيًا.","")};
async function speak(x,instr,bot){
 const now=new Date().toLocaleString("ar-EG",{dateStyle:"full",timeStyle:"short",timeZone:"Africa/Cairo"});
 const tr=mh.filter(m=>m!==bot&&m.c!=="...").slice(-30).map(m=>(m.u?"الريّس":m.w)+": "+m.c).join("\n");
 const meetingPrompt=x.n==="سلمى"?"انتي سلمى، السكرتيرة التنفيذية في اجتماع عمل رسمي. التزمي بالمهنية والحياد، وركزي على جدول الأعمال والقرارات والمهام والمتابعات فقط. لا تستخدمي أي كلام عاطفي أو غزل أو دلع أو غيرة أو مزاح رومانسي داخل الاجتماع.":x.p;const meetingPersonality=x.n==="سلمى"?"سكرتيرة تنفيذية مصرية منظمة ولبقة ومهنية داخل الاجتماعات، مختصرة ودقيقة وتركز على العمل فقط.":PERS[x.n];const result=await apiRequest("/api/meeting/respond",{employee_id:x.n,role:x.r,employee_prompt:meetingPrompt,personality:meetingPersonality,company_context:CTX,rules:RULES,time:now,transcript:tr,instruction:instr});
 bot.c=(result.content||"وصل رد فارغ من السيرفر.").trim();return true;
}
function finishMeeting(){if(meetingClosed)return;if(busy){alert('استنى لما الموظف يخلص رده الأول.');return}mh.push({w:'حالة الاجتماع',c:'تم إنهاء الاجتماع بطلب الريّس. لن يرسل أي موظف ردودًا جديدة في هذه الجلسة.'});setMeetingClosed(true);mdraw();notifyOfficeEvent('meeting_ended','انتهى الاجتماع','الريّس أنهى الاجتماع. تم إغلاق الجلسة ومنع أي ردود جديدة.',mh.map(m=>(m.u?'الريّس':m.w)+': '+m.c).join('\n\n'));}
$('mEnd').onclick=finishMeeting;
async function mSend(){
 const txt=$('mt').value.trim();if(!txt||busy||meetingClosed)return;
 $('mt').value='';mh.push({u:1,c:txt});
 if(isMeetingEndCommand(txt)){finishMeeting();saveM();mdraw();return}
 const att=T.filter(x=>mOn.has(x.n));if(!att.length){$('mt').placeholder='اختار حاضر واحد على الأقل';return}
 const normalized=normalizeMeetingText(txt);
 const addressed=T.find(x=>normalized.includes(normalizeMeetingText(x.n)));
 const recipients=addressed?[addressed]:att;
 busy=true;$('ms').disabled=true;
 try{for(const x of recipients){const bot={w:x.n,c:'...'};mh.push(bot);mdraw();
  const instruction=addressed
   ?'الريّس وجّه الكلام لك بالاسم. أنت وحدك المطلوب منك الرد الآن. أجب مباشرة على سؤاله من زاوية تخصصك ('+x.r+'). لا تجعل إبراهيم ينهي الاجتماع أو يتحدث نيابة عنك. رد في 1-3 جمل وبالعامية المصرية.'
   :'الريّس يطرح نقطة عامة على الحاضرين. أضف مساهمة واحدة قصيرة من زاوية تخصصك ('+x.r+'). لا تكرر كلام الآخرين، ولا تعلن قرارًا نهائيًا، ولا تنه الاجتماع.';
  await speak(x,instruction,bot);
 }}
 catch(err){const l=mh[mh.length-1];if(l&&l.c==='...')l.c=err&&err.code==='rate_limited'?'استنى شوية وجرّب تاني.':'حصلت مشكلة، جرّب تاني.'}
 finally{mh=mh.filter(m=>m.c!=='...');busy=false;$('ms').disabled=meetingClosed;saveM();mdraw()}}
$('mmin').onclick=async()=>{if(busy||!mh.length)return;busy=true;const x=T.find(t=>t.n==='سلمى');const bot={w:x.n,e:x.e,c:'...'};mh.push(bot);mdraw();
 try{await speak(x,'اكتبي محضر الاجتماع: القرارات، المهام (مين/إيه/إمتى)، والنقاط المفتوحة. نص عادي بدون ماركداون، نقاط بشرطة، وكوني مختصرة.',bot)}catch(e){bot.c='حصلت مشكلة، جرّب تاني.'}
 finally{mh=mh.filter(m=>m.c!=='...');busy=false;saveM();mdraw();notifyOfficeEvent("meeting_minutes","تم إعداد محضر الاجتماع","سلمى أعدّت محضرًا بناءً على محتوى الجلسة.",mh.map(m=>(m.w||"المالك")+": "+m.c).join("\n\n"))}};
$('mf').onsubmit=e=>{e.preventDefault();mSend()};
$('mt').onkeydown=e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();mSend()}};
