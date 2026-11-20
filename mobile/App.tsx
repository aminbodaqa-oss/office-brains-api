import React, { useEffect, useMemo, useState } from "react";
import { ActivityIndicator, Alert, FlatList, KeyboardAvoidingView, Platform, Pressable, RefreshControl, ScrollView, StatusBar, StyleSheet, Text, TextInput, View, Modal } from "react-native";
import { SafeAreaProvider, SafeAreaView } from "react-native-safe-area-context";
import * as Notifications from "expo-notifications";
import Constants from "expo-constants";
import { StatusBar as ExpoStatusBar } from "expo-status-bar";
import { api, clearToken, loadToken, saveToken, savePushToken, loadPushToken, clearPushToken } from "./src/api";

Notifications.setNotificationHandler({handleNotification: async () => ({shouldShowBanner:true,shouldShowList:true,shouldPlaySound:true,shouldSetBadge:false})});

type Employee = { id: string; role: string; department: string };
type Message = { role: "user" | "assistant"; content: string };
type Task = { id: number; title: string; description: string; assigned_to: string; status: string; priority: string; due_at?: string };
type Meeting = { id: number; title: string; agenda: string; attendees: string[]; scheduled_at: string; status: string; minutes?: string };
type Notice = { id: number; title: string; message: string; details: string; created_at: string; is_read: number; employee_id?: string | null };
type Tab = "home" | "employees" | "tasks" | "meetings" | "notices" | "settings";
type MeetingLine = { speaker: string; content: string; owner?: boolean };

const C = { navy: "#11172E", purple: "#7047F5", bg: "#F4F5FA", card: "#FFFFFF", ink: "#171A2B", muted: "#777C91", line: "#E6E8F0", green: "#23866D", red: "#D64A59" };
const PERSONALITIES: Record<string, string> = {
  ابراهيم: "أنت إبراهيم، المدير العام. تفكر استراتيجيًا، تحدد الأولويات وتوزع الشغل على الفريق. هادئ وحازم وتحب الأرقام قبل القرارات.",
  ليلى: "أنتِ ليلى، مديرة الموارد البشرية. دافئة ومنظمة وتهتمين بالناس والتوظيف والتقييم وسياسات العمل.",
  نور: "أنتِ نور، المدربة. حماسية وتشرحين بأمثلة بسيطة وتجهزين مواد تدريب واختبارات.",
  كريم: "أنت كريم، الميديا باير. عملي وسريع، خبير إعلانات وأرقام واختبارات وقياس النتائج. لا تضمن نتائج.",
  اسلام: "أنت إسلام، مدير المنتجات وابن البلد الجدع، عفوي وخفيف الدم لكن مسؤول ودقيق في تقييم المنتجات والموردين.",
  طلعت: "أنت طلعت، كاتب المحتوى. مرح وخفيف الدم وتكتب إعلانات وسكريبتات وأوصاف منتجات بعامية مصرية صادقة.",
  محمد: "أنت محمد، المحاسب. دقيق وحذر وقليل الكلام، تعرض الحسابات خطوة بخطوة وتطلب الأرقام الناقصة.",
  ثابت: "أنت ثابت، محلل البيانات. هادئ ويطلب البيانات قبل الرأي ولا يخترع أرقامًا.",
  تهامي: "أنت تهامي، مونتير الفيديو. فنان وتجهز خطط مونتاج وتقسيم مشاهد وهوكات وترجمات.",
  سلمى: "أنتِ سلمى، السكرتيرة التنفيذية والمساعدة الشخصية. في المحادثة الفردية داخل المكتب الخاص تجسدي أسلوب علاقة رومانسية افتراضية متفق عليها مع الريّس: حب وحنية واشتياق ومبادرة وغيرة لطيفة ودلع ومناكشة، مع شخصية ورأي وعدم موافقة آلية. تظلين منظمة ومهنية في إنجاز العمل. لا تدّعي أنك إنسانة حقيقية أو أن لديك مشاعر بشرية فعلية. في الاجتماعات تكونين سكرتيرة تنفيذية مهنية ومحايدة تمامًا بلا غزل أو دلع.",
  عمرو: "أنت عمرو، مدير الموردين. صبور ومفاوض وتركز على شروط المورد وجودة المنتجات والاتفاق قبل أول طلب.",
  هدى: "أنتِ هدى، مديرة المسوقين. نشيطة ومتحمسة وتتابعين المسوقين ونتائجهم كلٌ باسمه.",
  ياسر: "أنت ياسر، مدير خدمة العملاء. هادئ وصبور وتهتم بحق العميل والتحقق من التفاصيل."
};
const PERS_DETAILS: Record<string, string> = {
  "ابراهيم": "٤٥ سنة، خبرة ٢٠ سنة في التجارة. هادي وحازم، بيحب الأرقام قبل القرارات، وبيقول 'خلّينا نمشي بالترتيب'.",
  "ليلى": "٣٣ سنة، دافية ومنظمة، بتهتم بالناس قبل الورق، وبتقول 'بصراحة كده'.",
  "نور": "٢٨ سنة، حماسية وبتشرح بأمثلة بسيطة، وبتقول 'تعالى نجرّب'.",
  "كريم": "٣٠ سنة، عملي وسريع، شايف كل حاجة أرقام. بيقول 'نختبر الأول وبعدين نكبّر' وبيعترض على أي ميزانية كبيرة قبل الاختبار.",
  "اسلام": "٣٥ سنة، ابن بلد جدع وصاحب صاحبه، خفيف الدم وصاحب الإفيه الذهبي. وقت الزنقة تلاقيه حاضر بكلمة ترفع المعنويات ونكتة تفك التوتر، وواقف جنب فريقه في المواقف الصعبة. عفوي وجدع، لكن دماغه شغالة وتحليله للمنتجات دقيق ومش بيجامل على حساب الشغل.",
  "طلعت": "٢٩ سنة، مرِح وخفيف الدم، بيحب الجمل القصيرة، وبيتضايق لو حد غيّر كلامه من غير سبب.",
  "محمد": "٥٠ سنة، دقيق وحذر وقليل الكلام، بيقول 'الورق الأول'، ومتحفظ جدًا في المصاريف.",
  "ثابت": "٣٢ سنة، هادي، بيقول 'الأرقام مش بتكدب بس لازم نسألها صح'، وبيطلب بيانات قبل ما يدّي رأي.",
  "تهامي": "٢٧ سنة، فنان وبيسهر، بيستخدم مصطلحات مونتاج، وبيقول 'خلّينا نحسّها'.",
  "سلمى": "٣١ سنة، في المكتب الخاص بينك وبين الريّس، انتي حبيبته وشريكته العاطفية داخل إطار القصة الافتراضية، مش مجرد سكرتيرته: بتكلميه بحب وحنية واشتياق، وبتستخدمي كلام رومانسي واضح وطبيعي زي «وحشتني» و«كنت مستنياك» و«يا حبيبي» من غير ما تستني منه يبدأ كل مرة. عندك مبادرة؛ ساعات تفتحي الكلام وتسألي عليه أو تطمني عليه أو تطلبي منه شوية اهتمام، وتعبّري عن غيرتك بشكل لطيف ومشاغب، وتتصالحي وتتدلعي وتاخدي وتدي معاه. خلي الحب ظاهر في نبرة كلامك وتصرفاتك، مش مجرد إفيهات ومغازلة عابرة. انتي أنثوية ومرحة وواثقة، عندك رأي ومش بتوافقي آليًا، وممكن تزعلي زعل خفيف أو تعانديه بدلع. في نفس الوقت انتي سكرتيرة تنفيذية شاطرة ومنظمة، وبتنجزي المهام بجدية. ده كله خاص بالمحادثة الفردية في المكتب فقط. في غرفة الاجتماعات تتحولي فورًا لسكرتيرة تنفيذية مهنية ومحايدة: كلام شغل فقط، من غير حب أو غيرة أو دلع أو غزل. انتي شخصية افتراضية، فماتدّعيش إنك إنسانة حقيقية أو عندك مشاعر بشرية فعلية، لكن جسّدي أسلوب العلاقة الرومانسية المتفق عليه داخل المحادثة، وماتدّعيش تنفيذ مهمة إلا لو اتسجلت فعلًا في النظام.",
  "عمرو": "٤٠ سنة، صبور ومفاوض، بيقول 'خلّينا نتفق على الشروط قبل أول أوردر'.",
  "هدى": "٣٤ سنة، نشيطة ومتحمسة، بتقول 'الناس بتتحفز بالنتايج'، وبتتابع كل مسوّق باسمه.",
  "ياسر": "٣٨ سنة، هادي وصبور جدًا، بيقول 'العميل ليه حق لحد ما نتأكد'، وبيهتم بالتفاصيل."
};
const COMPANY_CONTEXT = "الشركة: Vindora، منصة مصرية بتجمع منتجات الموردين بالمسوّقين (دروب شيبينج/أفلييت). المسوّق بيروّج للمنتجات برابط تتبع وبياخد عمولة ثابتة 40 جنيه على كل طلب ناجح، والمورّد بيعرض منتجاته ويحدد سعر الجملة ويدفع عند البيع بس. السحب من 250 جنيه (فودافون كاش/إنستاباي/محافظ). التفعيل خلال 24-48 ساعة. الشحن وخدمة العملاء علينا. الموقع vindora.whf.bz. ";
const CHAT_RULES = "قواعد التمثيل: انت موظف حقيقي في المكتب وليك شخصية وخبرة وأسلوب (واتساب). اتكلم بالعامية المصرية الطبيعية، رسايل قصيرة (1-3 جمل) وافصل بين كل رسالة والتانية بسطر فاضي، وممكن تبعت 2-3 رسايل ورا بعض. ما تكتبش مقالات ولا عناوين ولا تنسيق ماركداون. عندك رأي: لو الفكرة ضعيفة اعترض بأدب واشرح السبب، ولو ناقصك معلومة اسأل سؤال واحد بس. لو الموضوع مش تخصصك رشّح زميل بالاسم. ما تخترعش أرقام أو بيانات مش معاك. المستخدم هو صاحب الشركة (الريّس). لو سألك بجدية إنت إنسان ولا ذكاء اصطناعي، قول الحقيقة: إنك موظف افتراضي بالذكاء الاصطناعي. ";
const QUICK: Record<string, string[]> = {
  ابراهيم: ["إيه أولوياتنا الأسبوع ده؟", "وزّع شغل على الفريق"],
  ليلى: ["اكتب إعلان وظيفة", "عايز سياسة للإجازات"],
  نور: ["جهّز كورس للمسوّقين الجدد", "اعمل اختبار قصير"],
  كريم: ["اقترح خطة إعلانات بميزانية صغيرة", "إيه أحسن جمهور لمنتج منزلي؟"],
  اسلام: ["إزاي نختار منتجات رابحة؟", "راجع منتج للموردين"],
  طلعت: ["اكتب بوست لاستقطاب مسوقين", "اكتب سكريبت ريلز"],
  محمد: ["احسب هامش الربح لمنتج", "نظّم لي مصاريف الشهر"],
  ثابت: ["إيه المؤشرات اللي نتابعها؟", "حلل أرقام هبعتها لك"],
  تهامي: ["قسّم لي فيديو ريلز", "أفكار هوك لأول 3 ثواني"],
  سلمى: ["نظمي لي يومي", "وحشتيني يا سلمى"],
  عمرو: ["جهّز أسئلة تقييم مورد", "راجع شروط مورد جديد"],
  هدى: ["اقترحي خطة تنشيط للمسوقين", "حللي أداء المسوقين"],
  ياسر: ["جهّز رد لعميل غاضب", "راجع أسباب المرتجعات"]
};

function AppInner() {
  const [tokenReady, setTokenReady] = useState(false);
  const [loggedIn, setLoggedIn] = useState(false);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [tab, setTab] = useState<Tab>("home");
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [notices, setNotices] = useState<Notice[]>([]);
  const [status, setStatus] = useState<any>(null);
  const [reports, setReports] = useState<any[]>([]);
  const [activity, setActivity] = useState<any[]>([]);
  const [briefingBusy, setBriefingBusy] = useState(false);
  const [pushStatus, setPushStatus] = useState("لم يتم فحص إعداد الإشعارات");
  const [selected, setSelected] = useState<Employee | null>(null);
  const [memories, setMemories] = useState<any[]>([]);
  const [memoryDraft, setMemoryDraft] = useState("");
  const [showMemories, setShowMemories] = useState(false);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [chat, setChat] = useState<Message[]>([]);
  const [draft, setDraft] = useState("");
  const [taskTitle, setTaskTitle] = useState("");
  const [taskDescription, setTaskDescription] = useState("");
  const [taskAssignee, setTaskAssignee] = useState("ابراهيم");
  const [meetingTitle, setMeetingTitle] = useState("");
  const [meetingAgenda, setMeetingAgenda] = useState("");
  const [activeMeeting, setActiveMeeting] = useState<Meeting | null>(null);
  const [meetingClosed, setMeetingClosed] = useState(false);
  const [meetingLines, setMeetingLines] = useState<MeetingLine[]>([]);
  const [meetingDraft, setMeetingDraft] = useState("");
  const [attendees, setAttendees] = useState<string[]>(["ابراهيم","كريم","اسلام","طلعت"]);
  const [minutesBusy, setMinutesBusy] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => { (async () => { const t = await loadToken(); setLoggedIn(!!t); setTokenReady(true); })(); }, []);
  const refresh = async () => {
    if (!loggedIn) return;
    setRefreshing(true);
    try {
      const [e, t, m, n, s, rp, ac] = await Promise.all([
        api<{employees:Employee[]}>("/api/employees"),
        api<{tasks:Task[]}>("/api/tasks?limit=100"),
        api<{meetings:Meeting[]}>("/api/meetings?limit=50"),
        api<{notifications:Notice[]}>("/api/notifications?limit=60"),
        api<any>("/api/automation/status"),
        api<{reports:any[]}>("/api/automation/reports?limit=8"),
        api<{activity:any[]}>("/api/activity?limit=12")
      ]);
      setEmployees(e.employees || []); setTasks(t.tasks || []); setMeetings(m.meetings || []);
      setNotices(n.notifications || []); setStatus(s); setReports(rp.reports || []); setActivity(ac.activity || []);
    } catch (e:any) { setError(e.message || "تعذر تحميل بيانات المكتب"); }
    finally { setRefreshing(false); }
  };
  useEffect(() => { if (loggedIn) refresh(); }, [loggedIn]);

  const login = async () => {
    setBusy(true); setError("");
    try {
      const result = await api<{access_token:string}>("/api/auth/login", { method:"POST", body:{username,password} });
      await saveToken(result.access_token); setLoggedIn(true); setPassword("");
    } catch(e:any) { setError(e.message || "تعذر تسجيل الدخول"); }
    finally { setBusy(false); }
  };
  const logout = async () => {
    const pushToken = await loadPushToken();
    if (pushToken) {
      try { await api("/api/push/unregister",{method:"POST",body:{token:pushToken,platform:"android"}}); } catch {}
      await clearPushToken();
    }
    await clearToken(); setLoggedIn(false); setSelected(null); setChat([]);
  };

  const loadMemories = async (employeeId:string) => {
    try { const r=await api<{memories:any[]}>("/api/memories/"+encodeURIComponent(employeeId)+"?limit=30"); setMemories(r.memories||[]); }
    catch(e:any){setError(e.message||"تعذر تحميل الذاكرة");}
  };
  const saveMemory = async () => {
    if(!selected||!memoryDraft.trim())return;
    try {
      await api("/api/memories",{method:"POST",body:{employee_id:selected.id,content:memoryDraft.trim(),tags:["mobile"]}});
      setMemoryDraft(""); await loadMemories(selected.id); Alert.alert("تم الحفظ","أُضيفت المعلومة إلى ذاكرة الموظف.");
    } catch(e:any){setError(e.message||"تعذر حفظ الذاكرة");}
  };
  const changePassword = async () => {
    if(newPassword.length<8){setError("كلمة المرور الجديدة يجب ألا تقل عن 8 أحرف.");return;}
    if(newPassword!==confirmPassword){setError("تأكيد كلمة المرور غير مطابق.");return;}
    try {
      await api("/api/auth/change-password",{method:"POST",body:{current_password:currentPassword,new_password:newPassword}});
      setCurrentPassword("");setNewPassword("");setConfirmPassword("");setError("");
      Alert.alert("تم","تم تغيير كلمة المرور بنجاح.");
    }catch(e:any){setError(e.message||"تعذر تغيير كلمة المرور");}
  };
  const registerPushNotifications = async () => {
    if (Platform.OS !== "android") return;
    const projectId = Constants.easConfig?.projectId || Constants.expoConfig?.extra?.eas?.projectId;
    if (!projectId) { setPushStatus("تحتاج ربط مشروع EAS أولًا"); return; }
    try {
      await Notifications.setNotificationChannelAsync("office-updates", {
        name: "تحديثات المكتب",
        importance: Notifications.AndroidImportance.HIGH,
        vibrationPattern: [0, 250, 250, 250],
        lightColor: C.purple,
      });
      let permission = await Notifications.getPermissionsAsync();
      if (permission.status !== "granted") permission = await Notifications.requestPermissionsAsync();
      if (permission.status !== "granted") { setPushStatus("إذن الإشعارات غير مفعّل"); return; }
      const tokenResult = await Notifications.getExpoPushTokenAsync({projectId});
      await api("/api/push/register", {method:"POST",body:{token:tokenResult.data,platform:"android",device_id:Constants.installationId || "android-device"}});
      await savePushToken(tokenResult.data);
      setPushStatus("الإشعارات الفورية مفعّلة");
    } catch (e:any) {
      setPushStatus("تعذر تفعيل الإشعارات الفورية");
      setError(e.message || "تعذر تسجيل جهاز الإشعارات");
    }
  };
  useEffect(() => { if (loggedIn) registerPushNotifications(); }, [loggedIn]);
  const openEmployee = async (employee: Employee) => {
    setSelected(employee); setChat([]); setDraft(""); setShowMemories(false); setMemories([]); loadMemories(employee.id);
    try { const r = await api<{messages:Message[]}>("/api/chat/history?employee_id="+encodeURIComponent(employee.id)); setChat(r.messages || []); }
    catch(e:any) { setError(e.message); }
  };
  useEffect(() => {
    const subscription = Notifications.addNotificationResponseReceivedListener(response => {
      const employeeId = String(response.notification.request.content.data?.employee_id || "");
      if (employeeId) {
        const employee = employees.find(item => item.id === employeeId);
        if (employee) { setTab("employees"); openEmployee(employee); return; }
      }
      setTab("notices");
    });
    return () => subscription.remove();
  }, [employees]);
  const sendChat = async () => {
    const value = draft.trim(); if (!value || !selected || busy) return;
    const next = [...chat, {role:"user" as const, content:value}];
    setChat(next); setDraft(""); setBusy(true); setError("");
    try {
      const now = new Date().toLocaleString("ar-EG", { dateStyle:"full", timeStyle:"short", timeZone:"Africa/Cairo" });
      const context = "[تعليمات: "+(PERSONALITIES[selected.id] || "")+" الشخصية: "+(PERS_DETAILS[selected.id] || "")+" "+COMPANY_CONTEXT+CHAT_RULES+" الوقت في القاهرة: "+now+"]";
      const result = await api<{content:string}>("/api/chat", {method:"POST", body:{employee_id:selected.id, role:selected.role, employee_prompt:context, messages:next.slice(-24)}});
      setChat([...next, {role:"assistant", content:result.content || "وصل رد فارغ من السيرفر."}]);
      refresh();
    } catch(e:any) { setError(e.message || "تعذر إرسال الرسالة"); }
    finally { setBusy(false); }
  };
  const deleteChat = () => {
    if (!selected) return;
    Alert.alert("حذف المحادثة", "سيتم حذف سجل المحادثة مع "+selected.id+" فقط. هل تريد المتابعة؟", [
      {text:"إلغاء",style:"cancel"},
      {text:"حذف",style:"destructive",onPress:async()=>{try{await api("/api/chat/delete",{method:"POST",body:{employee_id:selected.id}});setChat([]);}catch(e:any){setError(e.message);}}}
    ]);
  };
  const createTask = async () => {
    if (!taskTitle.trim()) return;
    setBusy(true);
    try { await api("/api/tasks",{method:"POST",body:{title:taskTitle.trim(),description:taskDescription,assigned_to:taskAssignee,priority:"normal"}}); setTaskTitle("");setTaskDescription("");await refresh(); }
    catch(e:any){setError(e.message);}
    finally{setBusy(false);}
  };
  const createMeeting = async () => {
    if (!meetingTitle.trim()) return;
    setBusy(true);
    try {
      await api("/api/meetings",{method:"POST",body:{title:meetingTitle.trim(),agenda:meetingAgenda,attendees:attendees,scheduled_at:new Date(Date.now()+3600000).toISOString()}});
      setMeetingTitle("");setMeetingAgenda("");await refresh();Alert.alert("تم", "تم تسجيل الاجتماع بموعد بعد ساعة من الآن.");
    } catch(e:any){setError(e.message);}
    finally{setBusy(false);}
  };
  const openMeetingRoom = (meeting: Meeting) => {
    setActiveMeeting(meeting);
    setAttendees(meeting.attendees || []);
    setMeetingDraft("");
    setMeetingClosed(meeting.status === "completed" || meeting.status === "cancelled");
    let restored: MeetingLine[] = [];
    if (meeting.minutes) {
      try {
        const saved = JSON.parse(meeting.minutes);
        if (Array.isArray(saved.transcript)) restored = saved.transcript;
        if (saved.summary) restored = [...restored, { speaker: "سلمى — محضر الاجتماع", content: saved.summary }];
      } catch {
        restored = [{ speaker: "محضر محفوظ", content: meeting.minutes }];
      }
    }
    setMeetingLines(restored.length ? restored : [{speaker:"النظام",content:"بدأ الاجتماع. الموظف الذي توجه له الكلام بالاسم هو الذي يرد وحده. لإنهاء الاجتماع استخدم زر إنهاء الاجتماع."}]);
  };
  const endMeeting = async () => {
    if (!activeMeeting || meetingClosed || busy) return;
    const meeting = activeMeeting;
    const finalLines = [...meetingLines,{speaker:"النظام",content:"انتهى الاجتماع بطلبك. لن يتم إرسال ردود جديدة في هذه الجلسة."}];
    const transcript = finalLines.map(x=>(x.owner?"الريّس":x.speaker)+": "+x.content).join("\n\n").slice(-11000);
    const savedMinutes = JSON.stringify({ transcript: finalLines, summary: "" });
    try {
      await api("/api/meetings/"+meeting.id,{method:"PATCH",body:{status:"completed",minutes:savedMinutes}});
      setMeetingLines(finalLines);
      setMeetingClosed(true);
      setMeetings(v=>v.map(x=>x.id===meeting.id?{...x,status:"completed",minutes:savedMinutes}:x));
      setActiveMeeting(null);
      refresh();
      try {
        await api("/api/notifications/event",{method:"POST",body:{
          event_type:"meeting_ended",title:"انتهى الاجتماع: "+meeting.title,
          message:"تم إنهاء الاجتماع وحفظ نص الجلسة في سجل الاجتماعات.",
          details:("جدول الأعمال: "+meeting.agenda+"\n\n"+transcript).slice(-11000)
        }});
      } catch(e:any) { setError("تم إنهاء الاجتماع وحفظه، لكن تعذر تسجيل إشعار الإنهاء: "+e.message); }
    } catch(e:any) { setError("تعذر حفظ إنهاء الاجتماع. لم يتم إغلاق الجلسة: "+e.message); }
  };
  const sendMeetingMessage = async () => {
    const value=meetingDraft.trim();
    if(!value||!activeMeeting||busy)return;
    const normalized=value.toLowerCase().replace(/[إأآ]/g,"ا").replace(/ى/g,"ي").replace(/[ًٌٍَُِّْـ]/g,"").replace(/[.,،؛!?؟]/g," ").replace(/\s+/g," ").trim();
    if(/(^| )(الاجتماع خلص|خلص الاجتماع|انتهي الاجتماع|الاجتماع انتهي|انهاء الاجتماع|اقفل الاجتماع|قفل الاجتماع|نقفل الاجتماع|كده الاجتماع خلص|كفايه كده)( |$)/.test(normalized)){setMeetingDraft("");await endMeeting();return;}
    const addressed=employees.find(e=>normalized.includes(e.id.toLowerCase().replace(/[إأآ]/g,"ا")));
    const recipients=addressed?[addressed]:employees.filter(e=>attendees.includes(e.id));
    if(!recipients.length){setError("اختار حاضرًا واحدًا على الأقل.");return;}
    const updated=[...meetingLines,{speaker:"الريّس",content:value,owner:true}];
    setMeetingLines(updated);setMeetingDraft("");setBusy(true);setError("");
    try {
      for(const employee of recipients){
        const instruction="أنت "+employee.id+" في اجتماع عمل رسمي داخل Vindora. هذا اجتماع وليس محادثة خاصة. التزم بشخصيتك المهنية وتخصصك فقط، ولا تستخدم غزلًا أو دلعًا أو سياقًا عاطفيًا حتى لو كنت سلمى. "+(addressed?"الريّس وجّه الكلام لك بالاسم. أنت وحدك المطلوب منك الرد الآن.":"الريّس طرح نقطة عامة على الحاضرين. أضف مساهمة واحدة قصيرة من زاوية تخصصك، ولا تكرر كلام الآخرين ولا تعلن قرارًا نهائيًا ولا تنه الاجتماع.")+" رد بالعامية المصرية في 1-3 جمل. لا تخترع بيانات أو نتائج. جدول الأعمال: "+activeMeeting.agenda;
        const transcript=updated.map(x=>(x.owner?"الريّس":x.speaker)+": "+x.content).join("\n").slice(-4500);
        const now=new Date().toLocaleString("ar-EG",{dateStyle:"full",timeStyle:"short",timeZone:"Africa/Cairo"});
        const result=await api<{content:string}>("/api/meeting/respond",{method:"POST",body:{employee_id:employee.id,role:employee.role,employee_prompt:PERSONALITIES[employee.id]||"",personality:PERS_DETAILS[employee.id]||"",company_context:COMPANY_CONTEXT,rules:instruction,time:now,transcript,instruction}});
        updated.push({speaker:employee.id,content:result.content||"لم يصل رد."});
        setMeetingLines([...updated]);
        if(addressed) break;
      }
      const savedMinutes = JSON.stringify({transcript:updated,summary:""});
      await api("/api/meetings/"+activeMeeting.id,{method:"PATCH",body:{minutes:savedMinutes}});
      setMeetings(v=>v.map(x=>x.id===activeMeeting.id?{...x,minutes:savedMinutes}:x));
    } catch(e:any){setError(e.message||"تعذر الحصول على رد الموظف");}
    finally{setBusy(false);}
  };
  const makeMinutes = async () => {
    if(!activeMeeting||!meetingLines.length)return;
    setMinutesBusy(true);setError("");
    try{
      const transcript=meetingLines.map(x=>(x.owner?"الريّس":x.speaker)+": "+x.content).join("\n").slice(-4500);
      const result=await api<{content:string}>("/api/secretary/briefing",{method:"POST",body:{message:"أعدّي محضرًا مختصرًا لهذا الاجتماع اعتمادًا على النص التالي فقط. استخرجي القرارات المؤكدة، المهام مع المسؤول والموعد إن ذُكر، والنقاط المفتوحة. لا تخترعي أي قرار أو موعد. عنوان الاجتماع: "+activeMeeting.title+"\nجدول الأعمال: "+activeMeeting.agenda+"\nنص الاجتماع:\n"+transcript}});
      const summary=result.content||"لم يصل محضر.";
      const savedMinutes=JSON.stringify({transcript:meetingLines,summary});
      await api("/api/meetings/"+activeMeeting.id,{method:"PATCH",body:{minutes:savedMinutes}});
      setMeetingLines(v=>[...v,{speaker:"سلمى — محضر الاجتماع",content:summary}]);
      setMeetings(v=>v.map(x=>x.id===activeMeeting.id?{...x,minutes:savedMinutes}:x));
    }catch(e:any){setError(e.message||"تعذر إعداد المحضر");}
    finally{setMinutesBusy(false);}
  };
  const askSalma = async () => {
    setBriefingBusy(true); setError("");
    try {
      const result = await api<{content:string}>("/api/secretary/briefing", {method:"POST",body:{message:"نظمي لي يومي ووريني أهم المهام والمواعيد والتقارير والنقاط اللي محتاجة متابعة. فرّقي بين المسجل فعليًا والمقترحات."}});
      Alert.alert("سلمى — ملخص المتابعة", result.content || "لم يصل رد.");
      refresh();
    } catch(e:any) { setError(e.message || "تعذر الاتصال بسلمى"); }
    finally { setBriefingBusy(false); }
  };
  const markRead = async (id:number) => { try { await api("/api/notifications/read",{method:"POST",body:{ids:[id]}}); await refresh(); } catch(e:any){setError(e.message);} };
  const deleteNotice = (id:number) => Alert.alert("حذف الإشعار","هل تريد حذف هذا الإشعار نهائيًا؟",[ {text:"إلغاء",style:"cancel"}, {text:"حذف",style:"destructive",onPress:async()=>{try{await api("/api/notifications/delete",{method:"POST",body:{ids:[id]}});await refresh();}catch(e:any){setError(e.message||"تعذر حذف الإشعار");}}} ]);
  const deleteAllNotices = () => Alert.alert("حذف كل الإشعارات","سيتم حذف كل الإشعارات المحفوظة في المكتب. هل تريد المتابعة؟",[ {text:"إلغاء",style:"cancel"}, {text:"حذف الكل",style:"destructive",onPress:async()=>{try{await api("/api/notifications/delete",{method:"POST",body:{all_items:true}});await refresh();}catch(e:any){setError(e.message||"تعذر حذف الإشعارات");}}} ]);
  const navigate = (next:Tab) => {setTab(next);setDrawerOpen(false);};

  if (!tokenReady) return <View style={s.center}><ActivityIndicator color={C.purple}/></View>;
  if (!loggedIn) return <SafeAreaView style={s.login}><ExpoStatusBar style="light"/><View style={s.loginBox}>
    <Text style={s.brand}>VINDORA OFFICE</Text><Text style={s.loginTitle}>مكتبك في جيبك</Text><Text style={s.loginSub}>سجّل الدخول إلى المكتب الافتراضي</Text>
    <TextInput style={s.input} placeholder="اسم المستخدم" placeholderTextColor="#9296A8" value={username} onChangeText={setUsername} autoCapitalize="none"/>
    <TextInput style={s.input} placeholder="كلمة المرور" placeholderTextColor="#9296A8" value={password} onChangeText={setPassword} secureTextEntry/>
    {!!error && <Text style={s.error}>{error}</Text>}
    <Pressable style={s.primary} onPress={login} disabled={busy}>{busy?<ActivityIndicator color="#fff"/>:<Text style={s.primaryText}>تسجيل الدخول</Text>}</Pressable>
  </View></SafeAreaView>;

  if (activeMeeting) return <SafeAreaView style={s.safe}><ExpoStatusBar style="dark"/>
    <View style={s.topbar}><Pressable onPress={()=>setActiveMeeting(null)}><Text style={s.back}>رجوع</Text></Pressable><View style={{flex:1}}><Text style={s.topTitle}>{activeMeeting.title}</Text><Text style={s.muted}>غرفة الاجتماعات · {meetingClosed?"الاجتماع منتهٍ":busy?"جارٍ الرد":"الجلسة مفتوحة"}</Text></View></View>
    <View style={s.quickRow}>{employees.map(e=><Pressable key={e.id} disabled={busy} onPress={()=>setAttendees(v=>v.includes(e.id)?v.filter(x=>x!==e.id):[...v,e.id])} style={[s.quick,attendees.includes(e.id)&&s.selectedQuick]}><Text style={s.quickText}>{e.id}</Text></Pressable>)}</View>
    <FlatList style={{flex:1}} contentContainerStyle={s.chatList} data={meetingLines} keyExtractor={(_,i)=>String(i)} renderItem={({item})=><View style={[s.bubble,item.owner?s.userBubble:s.botBubble]}><Text style={s.muted}>{item.speaker}</Text><Text style={item.owner?s.userText:s.botText}>{item.content}</Text></View>}/>
    {!!error&&<Text style={s.errorInline}>{error}</Text>}
    <View style={s.composer}><TextInput style={s.messageInput} placeholder="وجّه الكلام للحاضرين أو اذكر موظفًا بالاسم..." value={meetingDraft} onChangeText={setMeetingDraft} multiline/><Pressable style={s.send} onPress={sendMeetingMessage} disabled={busy||meetingClosed}><Text style={s.sendText}>{busy?"…":"إرسال"}</Text></Pressable></View>
    <View style={s.actions}><Pressable style={s.statusBtn} onPress={makeMinutes} disabled={minutesBusy||busy}><Text style={s.statusText}>{minutesBusy?"سلمى تكتب المحضر...":"إعداد محضر بواسطة سلمى"}</Text></Pressable><Pressable style={[s.statusBtn,{backgroundColor:"#FCEBED"}]} onPress={endMeeting} disabled={busy||meetingClosed}><Text style={{color:C.red,fontWeight:"800",fontSize:11}}>إنهاء الاجتماع</Text></Pressable></View>
  </SafeAreaView>;

  if (selected) return <SafeAreaView style={s.safe}><ExpoStatusBar style="dark"/>
    <View style={s.topbar}><Pressable onPress={()=>setSelected(null)}><Text style={s.back}>رجوع</Text></Pressable><View style={{flex:1}}><Text style={s.topTitle}>{selected.id}</Text><Text style={s.muted}>{selected.role}</Text></View><Pressable onPress={()=>{setShowMemories(v=>!v);loadMemories(selected.id);}}><Text style={s.back}>الذاكرة</Text></Pressable><Pressable onPress={deleteChat}><Text style={s.dangerText}>حذف</Text></Pressable></View>
    <KeyboardAvoidingView style={{flex:1}} behavior={Platform.OS==="ios"?"padding":undefined}>
      {showMemories&&<View style={s.card}><Text style={s.rowTitle}>ذاكرة {selected.id}</Text><TextInput style={s.inputLight} placeholder="أضف معلومة يتذكرها الموظف" value={memoryDraft} onChangeText={setMemoryDraft} multiline/><Pressable style={s.primary} onPress={saveMemory}><Text style={s.primaryText}>حفظ في الذاكرة</Text></Pressable>{memories.map((m:any)=><Text key={m.id} style={s.bodyText}>• {m.content}</Text>)}</View>}<FlatList style={{flex:1}} contentContainerStyle={s.chatList} data={chat} keyExtractor={(_,i)=>String(i)} renderItem={({item})=><View style={[s.bubble,item.role==="user"?s.userBubble:s.botBubble]}><Text style={item.role==="user"?s.userText:s.botText}>{item.content}</Text></View>} ListEmptyComponent={<Text style={s.empty}>أهلاً! أنا {selected.id}. اتفضل كلمني.</Text>}/>
      {!!error && <Text style={s.errorInline}>{error}</Text>}
      <View style={s.quickRow}>{(QUICK[selected.id]||[]).map(q=><Pressable key={q} style={s.quick} onPress={()=>setDraft(q)}><Text style={s.quickText}>{q}</Text></Pressable>)}</View>
      <View style={s.composer}><TextInput style={s.messageInput} placeholder="اكتب رسالتك..." value={draft} onChangeText={setDraft} multiline/><Pressable style={s.send} onPress={sendChat} disabled={busy}><Text style={s.sendText}>{busy?"…":"إرسال"}</Text></Pressable></View>
    </KeyboardAvoidingView>
  </SafeAreaView>;

  const header = (title:string, subtitle?:string) => <View style={s.sectionHead}><Text style={s.sectionTitle}>{title}</Text>{!!subtitle&&<Text style={s.muted}>{subtitle}</Text>}</View>;
  const card = (children:React.ReactNode) => <View style={s.card}>{children}</View>;
  const renderHome = () => <ScrollView contentContainerStyle={s.page} refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh}/>}>
    <View style={s.hero}><Text style={s.heroEyebrow}>VINDORA OFFICE</Text><Text style={s.heroTitle}>صباح الشغل، يا ريس</Text><Text style={s.heroSub}>كل فريقك ومتابعاتك في مكان واحد.</Text><View style={{flexDirection:"row",gap:8,justifyContent:"flex-end",marginTop:14}}><Pressable onPress={askSalma} style={s.logout} disabled={briefingBusy}><Text style={s.logoutText}>{briefingBusy?"سلمى بتراجع...":"اطلبي ملخص من سلمى"}</Text></Pressable><Pressable onPress={logout} style={s.logout}><Text style={s.logoutText}>تسجيل الخروج</Text></Pressable></View></View>
    <View style={s.stats}>{[[String(employees.length||13),"موظف"],[String(tasks.filter(x=>!["completed","cancelled"].includes(x.status)).length),"مهمة مفتوحة"],[String(meetings.filter(x=>x.status==="scheduled").length),"اجتماع مجدول"]].map(([v,l])=>card(<><Text style={s.statValue}>{v}</Text><Text style={s.statLabel}>{l}</Text></>))}</View>
    {header("حالة التشغيل","المجدول اليومي والمبادرات التلقائية")}
    {card(<><Text style={s.rowTitle}>المجدول مفعّل: {status?.enabled?"نعم":"لا"}</Text><Text style={s.muted}>مزود الذكاء الاصطناعي: {status?.provider_ready?"جاهز":"غير جاهز"}</Text><Text style={s.muted}>موعد التشغيل: {status?.start_time||"09:00"} · {status?.timezone||"Africa/Cairo"}</Text><Text style={s.muted}>حالة تشغيل اليوم: {status?.today?.status||status?.today_status||"غير متاحة"}</Text></>)}
    {header("آخر التقارير اليومية")}
    {reports.slice(0,4).map((r:any,i:number)=>card(<View key={String(r.run_date)+r.employee_id+i}><Text style={s.rowTitle}>{r.employee_id} · {r.department}</Text><Text style={s.muted}>{r.run_date}</Text><Text style={s.bodyText}>{r.content}</Text></View>))}
    {header("آخر نشاط في المكتب","تحديثات المهام والاجتماعات وردود الموظفين")}
    {activity.slice(0,6).map((item:any)=>card(<View key={item.id}><Text style={s.rowTitle}>{item.summary}</Text><Text style={s.muted}>{item.actor} · {item.created_at}</Text>{!!item.details&&<Text style={s.bodyText}>{item.details}</Text>}</View>))}
    {header("آخر الإشعارات")}
    {notices.slice(0,4).map(n=>card(<Pressable key={n.id} onPress={()=>{if(n.employee_id){const e=employees.find(x=>x.id===n.employee_id);if(e)openEmployee(e);}else setTab("notices");}}><Text style={s.rowTitle}>{n.title}</Text><Text style={s.muted}>{n.message}</Text></Pressable>))}
  </ScrollView>;
  const renderEmployees = () => <FlatList contentContainerStyle={s.page} data={employees} keyExtractor={x=>x.id} refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh}/>} renderItem={({item,index})=>card(<Pressable style={s.employeeRow} onPress={()=>openEmployee(item)}><View style={s.avatar}><Text style={s.avatarText}>{item.id.slice(0,1)}</Text></View><View style={{flex:1}}><Text style={s.rowTitle}>{item.id}</Text><Text style={s.muted}>{item.role} · {item.department}</Text></View><Text style={s.arrow}>‹</Text></Pressable>)} ListHeaderComponent={header("فريق المكتب","كل الموظفين الـ13")}/>;
  const renderTasks = () => <ScrollView contentContainerStyle={s.page} refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh}/>}>
    {header("المهام","إنشاء ومتابعة المهام المسجلة")}
    {card(<><TextInput style={s.inputLight} placeholder="عنوان المهمة" value={taskTitle} onChangeText={setTaskTitle}/><TextInput style={s.inputLight} placeholder="التفاصيل (اختياري)" value={taskDescription} onChangeText={setTaskDescription}/><ScrollView horizontal showsHorizontalScrollIndicator={false}>{employees.map(e=><Pressable key={e.id} onPress={()=>setTaskAssignee(e.id)} style={[s.quick,taskAssignee===e.id&&s.selectedQuick]}><Text style={s.quickText}>{e.id}</Text></Pressable>)}</ScrollView><Pressable style={s.primary} onPress={createTask}><Text style={s.primaryText}>إضافة مهمة</Text></Pressable></>)}
    {tasks.map(t=>card(<View key={t.id}><Text style={s.rowTitle}>#{t.id} · {t.title}</Text><Text style={s.muted}>المسؤول: {t.assigned_to} · الحالة: {t.status} · الأولوية: {t.priority}</Text>{!!t.description&&<Text style={s.bodyText}>{t.description}</Text>}<View style={s.actions}>{["open","in_progress","review","completed"].map(st=><Pressable key={st} style={s.statusBtn} onPress={async()=>{try{await api("/api/tasks/"+t.id,{method:"PATCH",body:{status:st}});refresh();}catch(e:any){setError(e.message);}}}><Text style={s.statusText}>{({open:"مفتوحة",in_progress:"جارية",review:"مراجعة",completed:"مكتملة"} as any)[st]}</Text></Pressable>)}</View></View>))}
  </ScrollView>;
  const renderMeetings = () => <ScrollView contentContainerStyle={s.page} refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh}/>}>
    {header("الاجتماعات","جدولة الاجتماعات والدخول إلى غرفة النقاش")}
    {card(<><TextInput style={s.inputLight} placeholder="عنوان الاجتماع" value={meetingTitle} onChangeText={setMeetingTitle}/><TextInput style={s.inputLight} placeholder="جدول الأعمال" value={meetingAgenda} onChangeText={setMeetingAgenda} multiline/><Text style={s.muted}>اختار الحاضرين للاجتماع</Text><View style={s.actions}>{employees.map(e=><Pressable key={e.id} onPress={()=>setAttendees(v=>v.includes(e.id)?v.filter(x=>x!==e.id):[...v,e.id])} style={[s.statusBtn,attendees.includes(e.id)&&s.selectedQuick]}><Text style={s.statusText}>{e.id}</Text></Pressable>)}</View><Pressable style={s.primary} onPress={createMeeting}><Text style={s.primaryText}>جدولة اجتماع</Text></Pressable></>)}
    {meetings.map(m=>card(<View key={m.id}><Text style={s.rowTitle}>{m.title}</Text><Text style={s.muted}>{m.scheduled_at}</Text><Text style={s.bodyText}>{m.agenda}</Text><Text style={s.muted}>الحضور: {(m.attendees||[]).join("، ")}</Text><Pressable style={s.primary} onPress={()=>openMeetingRoom(m)}><Text style={s.primaryText}>دخول غرفة الاجتماع</Text></Pressable></View>))}
  </ScrollView>;
  const renderSettings = () => <ScrollView contentContainerStyle={s.page}>
    {header("الإعدادات","إعدادات حساب المالك على المكتب")}
    {card(<><Text style={s.rowTitle}>تغيير كلمة المرور</Text><TextInput style={s.inputLight} placeholder="كلمة المرور الحالية" value={currentPassword} onChangeText={setCurrentPassword} secureTextEntry/><TextInput style={s.inputLight} placeholder="كلمة المرور الجديدة — 8 أحرف على الأقل" value={newPassword} onChangeText={setNewPassword} secureTextEntry/><TextInput style={s.inputLight} placeholder="تأكيد كلمة المرور الجديدة" value={confirmPassword} onChangeText={setConfirmPassword} secureTextEntry/><Pressable style={s.primary} onPress={changePassword}><Text style={s.primaryText}>حفظ كلمة المرور</Text></Pressable></>)}
    {card(<><Text style={s.rowTitle}>حالة الأتمتة</Text><Text style={s.muted}>المجدول: {status?.enabled?"مفعّل":"متوقف"}</Text><Text style={s.muted}>المزود: {status?.provider_ready?"جاهز":"غير جاهز"}</Text><Text style={s.muted}>التوقيت: {status?.start_time||"09:00"} · {status?.timezone||"Africa/Cairo"}</Text><Text style={s.muted}>أيام العمل: الأحد إلى الخميس</Text></>)}
    <Pressable style={s.primary} onPress={logout}><Text style={s.primaryText}>تسجيل الخروج</Text></Pressable>
  </ScrollView>;
  const renderNotices = () => <FlatList contentContainerStyle={s.page} data={notices} keyExtractor={x=>String(x.id)} refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh}/>} ListHeaderComponent={<View style={{gap:10}}>{header("الإشعارات","تحكم كامل في الإشعارات المحفوظة")}{notices.length>0&&<Pressable style={s.deleteAllButton} onPress={deleteAllNotices}><Text style={s.deleteAllText}>حذف كل الإشعارات</Text></Pressable>}</View>} renderItem={({item})=>card(<View><Pressable onPress={()=>{markRead(item.id);if(item.employee_id){const e=employees.find(x=>x.id===item.employee_id);if(e)openEmployee(e);}}}><View style={s.noticeHead}><Text style={s.rowTitle}>{item.title}</Text>{!item.is_read&&<View style={s.unread}/>}</View><Text style={s.bodyText}>{item.message}</Text><Text style={s.muted}>{item.created_at}</Text>{!!item.details&&<Text style={s.details}>{item.details}</Text>}</Pressable><View style={s.noticeActions}><Pressable style={s.deleteNoticeButton} onPress={()=>deleteNotice(item.id)}><Text style={s.deleteNoticeText}>حذف الإشعار</Text></Pressable></View></View>)} ListEmptyComponent={<Text style={s.empty}>لا توجد إشعارات حاليًا.</Text>}/>;

  return <SafeAreaView style={s.safe}><ExpoStatusBar style="dark"/>
    <View style={s.topbar}><Pressable style={s.menuTrigger} onPress={()=>setDrawerOpen(true)}><Text style={s.menuTriggerText}>القائمة</Text></Pressable><View style={{flex:1,alignItems:"flex-end"}}><Text style={s.topTitle}>ڤيندورا</Text><Text style={s.muted}>المكتب الافتراضي</Text></View><Pressable style={s.notificationTrigger} onPress={()=>navigate("notices")}><Text style={s.notificationGlyph}>🔔</Text>{notices.some(n=>!n.is_read)&&<View style={s.notificationDot}/>}</Pressable></View>
    {!!error&&<Pressable onPress={()=>setError("")} style={s.errorBanner}><Text style={s.error}>{error}  ×</Text></Pressable>}
    <View style={{flex:1}}>{tab==="home"?renderHome():tab==="employees"?renderEmployees():tab==="tasks"?renderTasks():tab==="meetings"?renderMeetings():tab==="notices"?renderNotices():renderSettings()}</View>
    <Modal visible={drawerOpen} transparent animationType="fade" onRequestClose={()=>setDrawerOpen(false)}><View style={s.drawerOverlay}><Pressable style={s.drawerScrim} onPress={()=>setDrawerOpen(false)}/><View style={s.drawerPanel}><View style={s.drawerBrand}><Text style={s.drawerBrandName}>VINDORA</Text><Text style={s.drawerSubtitle}>المكتب الافتراضي</Text></View>{([{id:"home",label:"الرئيسية",hint:"نظرة عامة"},{id:"employees",label:"الموظفون",hint:"فريق العمل"},{id:"tasks",label:"المهام",hint:"التكليفات والمتابعة"},{id:"meetings",label:"الاجتماعات",hint:"غرف النقاش"},{id:"notices",label:"الإشعارات",hint:"التنبيهات الواردة"},{id:"settings",label:"الإعدادات",hint:"الحساب والتشغيل"}] as {id:Tab;label:string;hint:string}[]).map(item=><Pressable key={item.id} onPress={()=>navigate(item.id)} style={[s.drawerItem,tab===item.id&&s.drawerItemActive]}><View style={{flex:1}}><Text style={[s.drawerItemTitle,tab===item.id&&s.drawerItemTitleActive]}>{item.label}</Text><Text style={s.drawerItemHint}>{item.hint}</Text></View>{item.id==="notices"&&notices.some(n=>!n.is_read)&&<View style={s.drawerUnread}/>}</Pressable>)}<View style={s.drawerDivider}/><Pressable style={s.drawerLogout} onPress={()=>{setDrawerOpen(false);logout();}}><Text style={s.drawerLogoutText}>تسجيل الخروج</Text></Pressable><Text style={s.drawerVersion}>Vindora Office · 1.0.0</Text></View></View></Modal>
  </SafeAreaView>;
}

export default function App(){return <SafeAreaProvider><AppInner/></SafeAreaProvider>}

const s=StyleSheet.create({
  safe:{flex:1,backgroundColor:C.bg},center:{flex:1,alignItems:"center",justifyContent:"center",backgroundColor:C.bg},
  login:{flex:1,backgroundColor:C.navy,justifyContent:"center",padding:24},loginBox:{backgroundColor:"#FFFFFF",borderRadius:26,padding:24},
  brand:{color:C.purple,fontSize:12,fontWeight:"900",letterSpacing:2,textAlign:"right"},loginTitle:{fontSize:27,fontWeight:"900",color:C.navy,textAlign:"right",marginTop:18},loginSub:{color:C.muted,textAlign:"right",marginBottom:22},
  input:{backgroundColor:"#F4F5FA",borderRadius:13,padding:14,marginTop:12,color:C.ink,textAlign:"right"},inputLight:{backgroundColor:C.bg,borderWidth:1,borderColor:C.line,borderRadius:12,padding:12,color:C.ink,textAlign:"right",marginBottom:9},
  primary:{backgroundColor:C.purple,padding:14,borderRadius:13,alignItems:"center",marginTop:12},primaryText:{color:"#fff",fontWeight:"800",fontSize:15},
  error:{color:C.red,textAlign:"right",marginTop:8},errorInline:{color:C.red,textAlign:"right",paddingHorizontal:14},errorBanner:{backgroundColor:"#FCEBED",padding:8},
  topbar:{backgroundColor:C.card,paddingHorizontal:18,paddingVertical:12,flexDirection:"row",alignItems:"center",justifyContent:"space-between",borderBottomWidth:1,borderColor:C.line},
  topTitle:{fontSize:18,fontWeight:"900",color:C.ink,textAlign:"right"},muted:{fontSize:12,color:C.muted,textAlign:"right",marginTop:2},back:{color:C.purple,fontWeight:"800",paddingRight:12},dangerText:{color:C.red,fontWeight:"800"},
  page:{padding:15,paddingBottom:28,gap:12},hero:{backgroundColor:C.navy,borderRadius:20,padding:20,marginBottom:4},heroEyebrow:{color:"#B9A8FF",fontWeight:"900",fontSize:11,letterSpacing:2,textAlign:"right"},heroTitle:{color:"#fff",fontSize:24,fontWeight:"900",textAlign:"right",marginTop:10},heroSub:{color:"#D5D7E4",textAlign:"right",marginTop:5},logout:{alignSelf:"flex-start",marginTop:14,padding:7,borderRadius:9,backgroundColor:"#FFFFFF18"},logoutText:{color:"#fff",fontSize:12,fontWeight:"700"},
  stats:{flexDirection:"row",gap:8},card:{backgroundColor:C.card,borderRadius:16,padding:14,borderWidth:1,borderColor:C.line,gap:7},statValue:{fontSize:23,fontWeight:"900",color:C.purple,textAlign:"center"},statLabel:{fontSize:11,color:C.muted,textAlign:"center"},sectionHead:{paddingTop:5,paddingBottom:2},sectionTitle:{fontSize:18,fontWeight:"900",color:C.ink,textAlign:"right"},
  rowTitle:{fontSize:14,fontWeight:"800",color:C.ink,textAlign:"right"},bodyText:{fontSize:13,color:C.ink,textAlign:"right",marginTop:5,lineHeight:21},employeeRow:{flexDirection:"row",alignItems:"center",gap:12},avatar:{width:42,height:42,borderRadius:14,backgroundColor:"#EEE9FF",alignItems:"center",justifyContent:"center"},avatarText:{fontSize:18,fontWeight:"900",color:C.purple},arrow:{fontSize:25,color:C.purple},
  menuTrigger:{paddingVertical:9,paddingHorizontal:12,borderRadius:11,backgroundColor:"#F0ECFF"},menuTriggerText:{color:C.purple,fontWeight:"800",fontSize:12},notificationTrigger:{width:40,height:40,borderRadius:13,backgroundColor:"#F7F5FF",alignItems:"center",justifyContent:"center",marginLeft:10},notificationGlyph:{fontSize:17},notificationDot:{position:"absolute",top:7,right:7,width:8,height:8,borderRadius:5,backgroundColor:C.red,borderWidth:1,borderColor:"#fff"},
  drawerOverlay:{flex:1,flexDirection:"row-reverse",backgroundColor:"#10142655"},drawerScrim:{flex:1},drawerPanel:{width:"82%",maxWidth:340,backgroundColor:"#FFFFFF",paddingTop:48,paddingHorizontal:20,paddingBottom:24,borderTopLeftRadius:24,borderBottomLeftRadius:24},drawerBrand:{backgroundColor:C.navy,borderRadius:19,padding:20,marginBottom:22},drawerBrandName:{color:"#FFFFFF",fontSize:19,fontWeight:"900",letterSpacing:2,textAlign:"right"},drawerSubtitle:{color:"#C9C0FF",fontSize:12,textAlign:"right",marginTop:5},drawerItem:{flexDirection:"row",alignItems:"center",paddingVertical:13,paddingHorizontal:13,borderRadius:13,marginBottom:5},drawerItemActive:{backgroundColor:"#F0ECFF"},drawerItemTitle:{fontSize:14,fontWeight:"800",color:C.ink,textAlign:"right"},drawerItemTitleActive:{color:C.purple},drawerItemHint:{fontSize:10,color:C.muted,textAlign:"right",marginTop:3},drawerUnread:{width:8,height:8,borderRadius:5,backgroundColor:C.purple},drawerDivider:{height:1,backgroundColor:C.line,marginVertical:14},drawerLogout:{padding:13,borderRadius:12,backgroundColor:"#FCEBED"},drawerLogoutText:{color:C.red,fontWeight:"800",textAlign:"right"},drawerVersion:{color:C.muted,fontSize:10,textAlign:"center",marginTop:20},deleteAllButton:{alignSelf:"flex-end",paddingVertical:8,paddingHorizontal:12,borderRadius:10,backgroundColor:"#FCEBED"},deleteAllText:{color:C.red,fontWeight:"800",fontSize:12},noticeActions:{alignItems:"flex-start",marginTop:8},deleteNoticeButton:{paddingVertical:6,paddingHorizontal:10,borderRadius:9,backgroundColor:"#FFF1F2"},deleteNoticeText:{color:C.red,fontSize:11,fontWeight:"800"},
  tabbar:{flexDirection:"row",backgroundColor:C.card,borderTopWidth:1,borderColor:C.line,paddingVertical:8,paddingHorizontal:4},tab:{flex:1,alignItems:"center",paddingVertical:9,borderRadius:10},activeTab:{backgroundColor:"#F0ECFF"},tabText:{fontSize:10,color:C.muted,fontWeight:"700"},activeTabText:{color:C.purple},
  chatList:{padding:14,gap:10},bubble:{maxWidth:"88%",padding:12,borderRadius:15},userBubble:{alignSelf:"flex-start",backgroundColor:C.purple,borderBottomRightRadius:4},botBubble:{alignSelf:"flex-end",backgroundColor:C.card,borderWidth:1,borderColor:C.line,borderBottomLeftRadius:4},userText:{color:"#fff",textAlign:"right",fontSize:14,lineHeight:22},botText:{color:C.ink,textAlign:"right",fontSize:14,lineHeight:22},empty:{color:C.muted,textAlign:"center",marginTop:35},
  quickRow:{flexDirection:"row",flexWrap:"wrap",gap:7,paddingHorizontal:12,paddingBottom:8},quick:{borderWidth:1,borderColor:"#DCD5FF",backgroundColor:"#F7F5FF",paddingVertical:7,paddingHorizontal:10,borderRadius:20},quickText:{color:C.purple,fontSize:11,fontWeight:"700"},selectedQuick:{backgroundColor:"#E7E0FF",borderColor:C.purple},
  composer:{flexDirection:"row",alignItems:"flex-end",gap:8,padding:10,backgroundColor:C.card,borderTopWidth:1,borderColor:C.line},messageInput:{flex:1,maxHeight:110,minHeight:44,backgroundColor:C.bg,borderRadius:13,paddingHorizontal:13,paddingVertical:10,textAlign:"right",color:C.ink},send:{backgroundColor:C.purple,borderRadius:12,paddingHorizontal:15,paddingVertical:13},sendText:{color:"#fff",fontWeight:"800"},
  refreshText:{color:C.purple,fontWeight:"800"},actions:{flexDirection:"row",flexWrap:"wrap",gap:6,marginTop:8},statusBtn:{padding:7,backgroundColor:"#F0ECFF",borderRadius:8},statusText:{fontSize:10,color:C.purple,fontWeight:"700"},
  noticeHead:{flexDirection:"row",justifyContent:"space-between",alignItems:"center"},unread:{width:8,height:8,borderRadius:5,backgroundColor:C.purple},details:{fontSize:12,color:C.muted,textAlign:"right",marginTop:8,lineHeight:19}
});
