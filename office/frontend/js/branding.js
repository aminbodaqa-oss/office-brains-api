(function () {
  const base = (window.OFFICE_API_URL || "").replace(/\/$/, "");
  const validColor = value => /^#[0-9a-fA-F]{6}$/.test(String(value || ""));
  function applySettings(settings) {
    Object.entries(settings || {}).forEach(([key, value]) => {
      if (!value) return;
      document.querySelectorAll('[data-brand-field="' + key + '"]').forEach(node => {
        if (node.tagName === "META") node.setAttribute("content", value);
        else node.textContent = value;
      });
      document.querySelectorAll('[data-brand-href="' + key + '"]').forEach(node => {
        node.setAttribute("href", value);
      });
    });
    const primary = settings.brand_primary;
    const accent = settings.brand_accent;
    const highlight = settings.brand_highlight;
    if (validColor(primary)) document.documentElement.style.setProperty("--brand-primary", primary);
    if (validColor(accent)) {
      document.documentElement.style.setProperty("--brand-accent", accent);
      document.documentElement.style.setProperty("--emerald", accent);
    }
    if (validColor(highlight)) {
      document.documentElement.style.setProperty("--brand-highlight", highlight);
      document.documentElement.style.setProperty("--gold", highlight);
    }
    if (validColor(accent) || validColor(highlight)) {
      const style = document.createElement("style");
      style.id = "saved-brand-overrides";
      const a = validColor(accent) ? accent : "#00A884";
      const h = validColor(highlight) ? highlight : "#F2B84B";
      style.textContent = ".primary{background:linear-gradient(120deg," + a + "," + a + ")!important;box-shadow:0 10px 30px " + a + "55!important}.btn:hover{border-color:" + h + "!important}.tag{border-color:" + a + "66!important;color:" + h + "!important;background:" + a + "15!important}.eyebrow,.step b,.avatar{color:" + h + "!important}.step{border-top-color:" + a + "88!important}";
      document.getElementById("saved-brand-overrides")?.remove();
      document.head.append(style);
    }
  }
  async function applySavedBrand() {
    if (!base) return;
    try {
      const response = await fetch(base + "/api/public/branding", {cache:"no-store"});
      if (!response.ok) return;
      const data = await response.json();
      if (data.logo_data_url) {
        document.querySelectorAll("[data-brand-logo]").forEach(img => { img.src = data.logo_data_url; });
        document.querySelectorAll("[data-brand-icon]").forEach(icon => { icon.href = data.logo_data_url; });
      }
      applySettings(data.settings || {});
      const platform = data.platform || {};
      const notice = document.getElementById("siteNotice");
      if (notice && platform.site_notice_enabled && platform.site_notice_text) {
        notice.textContent = platform.site_notice_text;
        notice.hidden = false;
      }
      if (platform.public_site_enabled === false) {
        const unavailable = document.getElementById("publicSiteUnavailable");
        if (unavailable) unavailable.hidden = false;
        Array.from(document.body.children).forEach(node => {
          if (node.id !== "publicSiteUnavailable" && node.tagName !== "SCRIPT") node.hidden = true;
        });
      }
    } catch (error) {
      /* Keep the static brand defaults when the API is offline. */
    }
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", applySavedBrand, {once:true});
  } else {
    applySavedBrand();
  }
})();
