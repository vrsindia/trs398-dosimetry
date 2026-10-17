(function () {
  var KEY = "dosepro_theme";

  function apply(theme) {
    if (theme !== "light" && theme !== "dark") theme = "dark";
    document.documentElement.setAttribute("data-theme", theme);
    try { localStorage.setItem(KEY, theme); } catch (e) {}
    var btn = document.getElementById("theme-toggle");
    if (btn) {
      btn.textContent = theme === "light" ? "Dark theme" : "Light theme";
      btn.setAttribute("aria-label", theme === "light" ? "Switch to dark theme" : "Switch to light theme");
    }
  }

  var saved = "dark";
  try {
    saved = localStorage.getItem(KEY) || "dark";
  } catch (e) {}

  // Apply immediately to avoid flash
  apply(saved);

  document.addEventListener("DOMContentLoaded", function () {
    apply(saved);
    var btn = document.getElementById("theme-toggle");
    if (btn) {
      btn.addEventListener("click", function () {
        var cur = document.documentElement.getAttribute("data-theme") || "dark";
        apply(cur === "dark" ? "light" : "dark");
      });
    }
  });
})();
