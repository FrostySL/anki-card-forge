"use strict";

// The local server appends a call with the bundled catalogs to this script.
function createReviewLocale(catalogs) {
  const storageKey = "card-forge.review-language";
  let language = "en";

  function catalogFor(tag) {
    try {
      const locale = new Intl.Locale(tag);
      let key = locale.language;
      if (key === "pt") key = "pt-BR";
      if (key === "zh") key = locale.maximize().script === "Hans" ? "zh-Hans" : "en";
      return Object.hasOwn(catalogs, key) ? key : "en";
    } catch {
      return "en";
    }
  }

  function t(key, values = {}) {
    const message = catalogs[language][key] ?? catalogs.en[key];
    return message.replace(/\{(\w+)\}/g, (token, name) => Object.hasOwn(values, name) ? values[name] : token);
  }

  function translatePage() {
    document.documentElement.lang = language;
    for (const element of document.querySelectorAll("[data-i18n]")) {
      element.textContent = t(element.dataset.i18n);
    }
    for (const attribute of ["title", "aria-label"]) {
      const marker = "data-i18n-" + attribute;
      for (const element of document.querySelectorAll("[" + marker + "]")) {
        element.setAttribute(attribute, t(element.getAttribute(marker)));
      }
    }
  }

  function syncLanguageHint() {
    const url = new URL(location.href);
    const hint = url.searchParams.get("lang");
    if (hint === null || catalogFor(hint) === language) return;
    url.searchParams.set("lang", language);
    history.replaceState(history.state, "", url);
  }

  function start(onChange) {
    const select = document.getElementById("ui-language");
    const hint = new URLSearchParams(location.search).get("lang");
    if (hint !== null) {
      language = catalogFor(hint);
    } else {
      try {
        const saved = localStorage.getItem(storageKey);
        if (Object.hasOwn(catalogs, saved)) language = saved;
      } catch { /* Language switching also works without browser storage. */ }
    }
    select.value = language;
    translatePage();
    // A prior card's history entry can still contain the old chat hint.
    // Keep the current choice on traversal so reloading that card agrees with its URL.
    window.addEventListener("popstate", syncLanguageHint);
    select.addEventListener("change", () => {
      if (!Object.hasOwn(catalogs, select.value)) return;
      language = select.value;
      try { localStorage.setItem(storageKey, language); }
      catch { /* Keep the choice for this page. */ }
      syncLanguageHint();
      translatePage();
      onChange();
    });
  }

  return {t, start, has: (key) => Object.hasOwn(catalogs.en, key)};
}
