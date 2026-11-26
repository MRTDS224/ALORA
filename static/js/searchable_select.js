/**
 * Progressive-enhancement accent-insensitive search for:
 * 1) <select data-searchable data-search-placeholder="...">
 * 2) <details class="multi-select"> with checkbox options and live summary
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

  // 1. Searchable single <select>
  document.querySelectorAll("select[data-searchable]").forEach(function (select) {
    var wrapper = document.createElement("div");
    wrapper.className = "searchable-select-wrap";

    var input = document.createElement("input");
    input.type = "search";
    input.className = "select-search-input";
    input.placeholder = select.getAttribute("data-search-placeholder") || "Rechercher…";
    input.setAttribute("aria-label", input.placeholder);
    input.autocomplete = "off";

    var allOptions = Array.prototype.slice.call(select.options).map(function (opt) {
      return {
        value: opt.value,
        text: opt.text,
        normText: norm(opt.text + " " + opt.value),
        selected: opt.selected,
      };
    });

    select.parentNode.insertBefore(wrapper, select);
    wrapper.appendChild(input);
    wrapper.appendChild(select);

    input.addEventListener("input", function () {
      var q = norm(input.value);
      var currentVal = select.value;
      var matches = allOptions.filter(function (o) {
        return !q || o.normText.indexOf(q) !== -1;
      });

      select.innerHTML = "";
      if (matches.length === 0) {
        var emptyOpt = document.createElement("option");
        emptyOpt.value = currentVal;
        emptyOpt.textContent = "Aucun résultat";
        emptyOpt.disabled = true;
        select.appendChild(emptyOpt);
        return;
      }

      var hasCurrent = false;
      matches.forEach(function (o) {
        var opt = document.createElement("option");
        opt.value = o.value;
        opt.textContent = o.text;
        if (o.value === currentVal) {
          opt.selected = true;
          hasCurrent = true;
        }
        select.appendChild(opt);
      });

      if (!hasCurrent && matches.length > 0) {
        select.value = matches[0].value;
      }
    });
  });

  // 2. Multi-select checkbox dropdown (<details class="multi-select">)
  document.querySelectorAll("details.multi-select").forEach(function (details) {
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

    // Close when clicking outside
    document.addEventListener("click", function (e) {
      if (details.open && !details.contains(e.target)) {
        details.open = false;
      }
    });
  });
})();
