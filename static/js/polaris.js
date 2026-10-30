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

(function weightGrids() {
  "use strict";

  // ---- 1. keyboard movement ----
  function inputAt(table, rowIndex, colIndex) {
    const row = table.tBodies[0] && table.tBodies[0].rows[rowIndex];
    if (!row) return null;
    const cell = row.cells[colIndex];
    return cell ? cell.querySelector("input.pl-cell__input:not([disabled])") : null;
  }

  document.addEventListener("keydown", function (event) {
    const input = event.target;
    if (!(input instanceof HTMLInputElement) || !input.classList.contains("pl-cell__input")) return;
    const td = input.closest("td");
    const tr = td.closest("tr");
    const table = tr.closest("table");
    const row = tr.sectionRowIndex;
    const col = td.cellIndex;
    const len = input.value.length;
    let target = null;
    switch (event.key) {
      case "Enter":
        event.preventDefault();                       // never submit the grid by accident
        target = inputAt(table, event.shiftKey ? row - 1 : row + 1, col);
        if (!target) input.blur();                     // last row: still triggers the cell check
        break;
      case "ArrowDown": target = inputAt(table, row + 1, col); break;
      case "ArrowUp": target = inputAt(table, row - 1, col); break;
      case "ArrowLeft": if (input.selectionStart === 0) target = inputAt(table, row, col - 1); break;
      case "ArrowRight": if (input.selectionEnd === len) target = inputAt(table, row, col + 1); break;
      default: return;
    }
    if (target) {
      event.preventDefault();
      target.focus();
      target.select();
    }
  });

  // ---- 2. save buttons ----
  function refreshSaveButtons() {
    document.querySelectorAll("form.pl-grid-form").forEach(function (form) {
      const invalid = form.querySelector(".pl-cell__input.is-invalid") !== null;
      form.querySelectorAll("[data-pl-save]").forEach(function (button) {
        button.disabled = invalid;
        button.title = invalid ? "Fix the cells marked in red first" : "";
      });
    });
  }

  document.addEventListener("input", function (event) {
    const input = event.target;
    if (!(input instanceof HTMLInputElement) || !input.classList.contains("pl-cell__input")) return;
    input.classList.remove("is-invalid");
    const form = input.closest("form.pl-grid-form");
    if (form) form.dataset.dirty = "1";
    refreshSaveButtons();
  });

  // ---- 3. tooltips ----
  function initTooltips() {
    if (!window.bootstrap) return;
    document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(function (el) {
      window.bootstrap.Tooltip.getOrCreateInstance(el);
    });
  }

  document.addEventListener("htmx:afterSwap", function () {
    refreshSaveButtons();
    initTooltips();
  });

  // ---- 4. unsaved changes ----
  document.addEventListener("submit", function (event) {
    if (event.target.matches && event.target.matches("form.pl-grid-form")) {
      event.target.dataset.dirty = "";
    }
  });

  window.addEventListener("beforeunload", function (event) {
    if (document.querySelector('form.pl-grid-form[data-dirty="1"]')) {
      event.preventDefault();
      event.returnValue = "";                         // older browsers need this to show the prompt
    }
  });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () { refreshSaveButtons(); initTooltips(); });
  } else {
    refreshSaveButtons();
    initTooltips();
  }
})();
