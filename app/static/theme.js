(function () {
  var KEY = "dosepro_theme";
  function apply(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    try { localStorage.setItem(KEY, theme); } catch (e) {}
    var btn = document.getElementById("theme-toggle");
    if (btn) btn.textContent = theme === "light" ? "Dark theme" : "Light theme";
  }
  var saved = "dark";
  try { saved = localStorage.getItem(KEY) || "dark"; } catch (e) {}
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
