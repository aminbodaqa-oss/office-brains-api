// Owner account settings: change password through the authenticated API.
const settingsPanel=document.getElementById("settingsPanel");
document.getElementById("settingsBtn").addEventListener("click",()=>{settingsPanel.style.display="flex";document.getElementById("passwordChangeMessage").textContent="";loadAutomationStatus();});
document.getElementById("closeSettings").addEventListener("click",()=>{settingsPanel.style.display="none";document.getElementById("changePasswordForm").reset();});
settingsPanel.addEventListener("click",e=>{if(e.target===settingsPanel){settingsPanel.style.display="none";document.getElementById("changePasswordForm").reset();}});
document.getElementById("changePasswordForm").addEventListener("submit",async e=>{
 e.preventDefault();const current=document.getElementById("currentPassword").value;const next=document.getElementById("newPassword").value;const confirmNext=document.getElementById("confirmNewPassword").value;const msg=document.getElementById("passwordChangeMessage");const btn=document.getElementById("savePasswordBtn");
 if(next.length<8){msg.textContent="كلمة المرور الجديدة لازم تكون 8 أحرف على الأقل.";return;}
 if(next!==confirmNext){msg.textContent="تأكيد كلمة المرور غير مطابق.";return;}
 if(current===next){msg.textContent="اختار كلمة مرور مختلفة عن الحالية.";return;}
 btn.disabled=true;msg.textContent="جارٍ تحديث كلمة المرور...";
 try{await apiRequest("/api/auth/change-password",{current_password:current,new_password:next});document.getElementById("changePasswordForm").reset();msg.textContent="تم تغيير كلمة المرور بنجاح.";msg.style.color="#16834a";}
 catch(err){msg.style.color="#c03950";msg.textContent=err.message||"تعذر تغيير كلمة المرور.";}
 finally{btn.disabled=false;}
});
