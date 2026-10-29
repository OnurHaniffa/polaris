// POlaris front-end glue. No framework: Bootstrap + HTMX do the work.
// Later stories add grid keyboard navigation (S2-06) and chart helpers (S3-02).
(function () {
  "use strict";

  // Theme toggle (light / dark), remembered per browser.
  document.addEventListener("click", function (event) {
    if (!event.target.closest("[data-pl-theme-toggle]")) return;
    var root = document.documentElement;
    var next = root.getAttribute("data-bs-theme") === "dark" ? "light" : "dark";
    root.setAttribute("data-bs-theme", next);
    try { localStorage.setItem("pl-theme", next); } catch (e) { /* private mode: ignore */ }
  });

  // Show any toasts the server rendered (Django messages), including ones HTMX swaps in.
  function showToasts(root) {
    root.querySelectorAll(".toast:not(.show)").forEach(function (el) {
      bootstrap.Toast.getOrCreateInstance(el).show();
    });
  }
  document.addEventListener("DOMContentLoaded", function () { showToasts(document); });
  document.body.addEventListener("htmx:afterSwap", function (event) { showToasts(event.target); });
})();
