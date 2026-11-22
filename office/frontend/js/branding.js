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
      const p = validColor(primary) ? primary : "#172A3A";
      style.textContent = ".primary{background:linear-gradient(120deg," + a + "," + a + ")!important;box-shadow:0 10px 30px " + a + "55!important}.btn:hover{border-color:" + h + "!important}.tag{border-color:" + a + "66!important;color:" + h + "!important;background:" + a + "15!important}.eyebrow,.step b,.avatar{color:" + h + "!important}.step{border-top-color:" + a + "88!important}.visual{background:linear-gradient(145deg," + p + "dd," + p + "bb)!important}.card{background:linear-gradient(145deg," + p + "," + p + ")!important}";
      document.getElementById("saved-brand-overrides")?.remove();
      document.head.append(style);
    }
  }
  function applyExperienceConfig(config) {
    if (!config || typeof config !== "object") return;
    const theme = config.theme || {};
    const vars = {
      primary:["--brand-primary","--primary"], accent:["--brand-accent","--emerald","--acc"],
      highlight:["--brand-highlight","--gold"], background:["--bg"],
      surface:["--card","--panel"], text:["--ink","--text"]
    };
    Object.entries(vars).forEach(([key, variables]) => {
      if (validColor(theme[key])) variables.forEach(variable =>
        document.documentElement.style.setProperty(variable, theme[key])
      );
    });
    applySettings({
      brand_primary:theme.primary,
      brand_accent:theme.accent,
      brand_highlight:theme.highlight
    });
    const fields = {
      site_name:config.site_name, page_title:config.page_title, meta_description:config.meta_description,
      hero_title:config.headline, hero_emphasis:config.headline_emphasis, hero_subtitle:config.subtitle,
      about_title:config.about_title, about_description:config.about_description,
      cta_title:config.cta_title, cta_description:config.cta_description,
      primary_cta_text:config.primary_cta_text, footer_text:config.footer_text
    };
    Object.entries(fields).forEach(([key,value]) => {
      if (!value) return;
      document.querySelectorAll('[data-brand-field="' + key + '"]').forEach(node => {
        if (node.tagName === "META") node.setAttribute("content", value);
        else node.textContent = value;
      });
    });
    if (config.page_title) document.title = config.page_title;
    if (config.meta_description) {
      const meta = document.querySelector('meta[name="description"]');
      if (meta) meta.setAttribute("content", config.meta_description);
    }
    if (config.primary_cta_url) {
      document.querySelectorAll('[data-brand-href="primary_cta_url"]').forEach(node => node.setAttribute("href", config.primary_cta_url));
    }
    if (Array.isArray(config.navigation)) {
      const nav = document.querySelector("nav[data-brand-navigation]");
      if (nav) {
        nav.replaceChildren();
        config.navigation.forEach(item => {
          const link = document.createElement("a");
          link.textContent = item.label;
          link.setAttribute("href", item.url);
          nav.append(link);
        });
      }
    }
    if (config.pages && typeof config.pages === "object") {
      Object.entries(config.pages).forEach(([pageId, page]) => {
        const section = Array.from(document.querySelectorAll("[data-page-key]")).find(node => node.dataset.pageKey === pageId);
        if (!section) return;
        section.hidden = page.visible === false;
        const heading = section.querySelector("h1,h2,h3");
        const description = section.querySelector("p");
        if (page.title && heading) heading.textContent = page.title;
        if (page.description && description) description.textContent = page.description;
      });
    }
    const fonts = {system:'system-ui,-apple-system,"Segoe UI",Tahoma,Arial,sans-serif',
      tajawal:'"Tajawal",Tahoma,Arial,sans-serif',cairo:'"Cairo",Tahoma,Arial,sans-serif',
      inter:'"Inter",Arial,sans-serif'};
    if (fonts[config.font_family]) { document.documentElement.style.setProperty("--office-font", fonts[config.font_family]); if (document.body) document.body.style.fontFamily = fonts[config.font_family]; }
    const root = document.documentElement;
    const densityScale = {compact:"0.86",comfortable:"1",spacious:"1.16"};
    const cornerRadius = {sharp:"7px",rounded:"14px",soft:"21px"};
    if (densityScale[config.density]) root.style.setProperty("--office-density-scale", densityScale[config.density]);
    if (cornerRadius[config.corner_style]) root.style.setProperty("--office-corner-radius", cornerRadius[config.corner_style]);
    root.dataset.officeDensity = densityScale[config.density] ? config.density : "comfortable";
    root.dataset.officeCorners = cornerRadius[config.corner_style] ? config.corner_style : "rounded";
    document.getElementById("office-experience-layout-overrides")?.remove();
    const style = document.createElement("style");
    style.id = "office-experience-layout-overrides";
    style.textContent = `
      :root{--office-density-scale:${densityScale[config.density] || "1"};--office-corner-radius:${cornerRadius[config.corner_style] || "14px"}}
      .panel,.card,.auth-card,.auth-panel,.customer-row,.readiness-row,.experience-preview,.visual,.dash,.cta,.stat,.task,.nav-item,.admin-sidebar,.topbar{border-radius:var(--office-corner-radius)!important}
      .panel,.card,.auth-card,.customer-row,.readiness-row{padding:calc(16px * var(--office-density-scale))}
      .admin-page .panel,.studio-form{gap:calc(16px * var(--office-density-scale))}
    `;
    document.head.append(style);
    const density = {compact:"52px",comfortable:"76px",spacious:"96px"};
    const corners = {sharp:"4px",rounded:"14px",soft:"22px"};
    if (density[config.density]) document.documentElement.style.setProperty("--office-section-space", density[config.density]);
    if (corners[config.corner_style]) document.documentElement.style.setProperty("--office-radius", corners[config.corner_style]);
  }
  async function applyOfficeExperience(surface) {
    if (!base) return null;
    try {
      const response = await fetch(base + "/api/public/experience?surface=" + encodeURIComponent(surface), {cache:"no-store"});
      if (!response.ok) return null;
      const data = await response.json();
      applyExperienceConfig(data.config || {});
      return data;
    } catch (_) { return null; }
  }
  window.applyOfficeExperience = applyOfficeExperience;
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
      const surface = location.pathname.includes("platform-admin.html") ? "super_admin" : (location.pathname.includes("/frontend/") ? "office_login" : "platform_site");
      await applyOfficeExperience(surface);
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
