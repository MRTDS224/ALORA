/**
 * Unified searchable dropdowns (zero external deps, 100% offline, accent-insensitive):
 * 1) <select data-searchable> -> enhanced into a single-box <details> dropdown with search inside
 * 2) <details class="multi-select"> -> multi-select checkbox dropdown with search inside
 */
(function () {
  function norm(str) {
    return (str || "")
      .toString()
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .trim();
  }

  // 1. Single-select searchable dropdown (search input lives INSIDE the dropdown)
  document.querySelectorAll("select[data-searchable]").forEach(function (select) {
    var placeholder = select.getAttribute("data-search-placeholder") || "Rechercher…";
    var optionsData = Array.prototype.slice.call(select.options).map(function (opt) {
      return {
        value: opt.value,
        text: opt.text,
        normText: norm(opt.text + " " + opt.value),
      };
    });

    var details = document.createElement("details");
    details.className = "multi-select single-select";

    var summary = document.createElement("summary");
    summary.className = "multi-select-summary";
    var summaryText = document.createElement("span");
    summaryText.className = "multi-select-summary-text";
    summary.appendChild(summaryText);

    var panel = document.createElement("div");
    panel.className = "multi-select-panel";

    var searchInput = document.createElement("input");
    searchInput.type = "search";
    searchInput.className = "multi-select-search";
    searchInput.placeholder = placeholder;
    searchInput.setAttribute("aria-label", placeholder);
    searchInput.autocomplete = "off";

    var list = document.createElement("div");
    list.className = "single-select-list";

    var emptyMsg = document.createElement("div");
    emptyMsg.className = "single-select-empty";
    emptyMsg.textContent = "Aucun résultat";
    emptyMsg.style.display = "none";

    var buttons = [];
    optionsData.forEach(function (o) {
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "single-select-option";
      btn.setAttribute("data-value", o.value);
      btn.setAttribute("data-norm", o.normText);
      btn.textContent = o.text;
      btn.addEventListener("click", function () {
        select.value = o.value;
        select.dispatchEvent(new Event("change", { bubbles: true }));
        syncActive();
        searchInput.value = "";
        filterItems("");
        details.open = false;
      });
      buttons.push(btn);
      list.appendChild(btn);
    });
    list.appendChild(emptyMsg);

    panel.appendChild(searchInput);
    panel.appendChild(list);
    details.appendChild(summary);
    details.appendChild(panel);

    function syncActive() {
      var currentVal = select.value;
      var currentLabel = "";
      buttons.forEach(function (btn) {
        var isMatch = btn.getAttribute("data-value") === currentVal;
        btn.classList.toggle("is-selected", isMatch);
        if (isMatch) currentLabel = btn.textContent;
      });
      summaryText.textContent = currentLabel || (optionsData[0] ? optionsData[0].text : "");
    }

    function filterItems(rawQuery) {
      var q = norm(rawQuery);
      var visible = 0;
      buttons.forEach(function (btn) {
        var match = !q || btn.getAttribute("data-norm").indexOf(q) !== -1;
        btn.style.display = match ? "" : "none";
        if (match) visible += 1;
      });
      emptyMsg.style.display = visible === 0 ? "block" : "none";
    }

    searchInput.addEventListener("input", function () {
      filterItems(searchInput.value);
    });

    details.addEventListener("toggle", function () {
      if (details.open) {
        setTimeout(function () { searchInput.focus(); }, 10);
      } else {
        searchInput.value = "";
        filterItems("");
      }
    });

    document.addEventListener("click", function (e) {
      if (details.open && !details.contains(e.target)) {
        details.open = false;
      }
    });

    details.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && details.open) {
        details.open = false;
        summary.focus();
      }
    });

    select.addEventListener("change", syncActive);

    // Hide native select while keeping it active for FormData and JS .value reads
    select.style.display = "none";
    select.parentNode.insertBefore(details, select.nextSibling);
    syncActive();
  });

  // 2. Multi-select checkbox dropdown (<details class="multi-select">)
  document.querySelectorAll("details.multi-select:not(.single-select)").forEach(function (details) {
    var summaryText = details.querySelector(".multi-select-summary-text");
    var placeholder = details.getAttribute("data-placeholder") || "Sélectionner…";
    var searchInput = details.querySelector(".multi-select-search");
    var items = Array.prototype.slice.call(details.querySelectorAll(".multi-select-option"));
    var checkboxes = Array.prototype.slice.call(details.querySelectorAll('input[type="checkbox"]'));

    function updateSummary() {
      if (!summaryText) return;
      var chosen = checkboxes
        .filter(function (cb) { return cb.checked; })
        .map(function (cb) { return cb.value; });
      if (chosen.length === 0) {
        summaryText.textContent = placeholder;
        summaryText.classList.add("is-placeholder");
      } else if (chosen.length <= 3) {
        summaryText.textContent = chosen.join(", ");
        summaryText.classList.remove("is-placeholder");
      } else {
        summaryText.textContent = chosen.slice(0, 2).join(", ") + " (+" + (chosen.length - 2) + ")";
        summaryText.classList.remove("is-placeholder");
      }
    }

    checkboxes.forEach(function (cb) {
      cb.addEventListener("change", updateSummary);
    });
    updateSummary();

    if (searchInput) {
      searchInput.addEventListener("input", function () {
        var q = norm(searchInput.value);
        items.forEach(function (label) {
          var text = norm(label.textContent);
          label.style.display = !q || text.indexOf(q) !== -1 ? "" : "none";
        });
      });
    }

    details.addEventListener("toggle", function () {
      if (details.open && searchInput) {
        setTimeout(function () { searchInput.focus(); }, 10);
      }
    });

    document.addEventListener("click", function (e) {
      if (details.open && !details.contains(e.target)) {
        details.open = false;
      }
    });
  });
})();
