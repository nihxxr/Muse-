(function () {
  // Fill the reviews box with sample reviews
  const fill = document.querySelector("[data-fill-samples]");
  const samples = document.getElementById("sample-reviews");
  if (fill && samples) {
    fill.addEventListener("click", () => {
      const box = document.getElementById("pasted");
      box.value = JSON.parse(samples.textContent).join("\n");
      const product = document.querySelector("input[name=product]");
      if (!product.value) product.value = "Beat massager";
      box.focus();
    });
  }

  // Show that a slow request is running
  const form = document.querySelector("[data-busy-form]");
  if (form) {
    form.addEventListener("submit", () => {
      const btn = form.querySelector("[data-busy-label]");
      btn.disabled = true;
      btn.textContent = btn.dataset.busyLabel + "…";
    });
  }

  function copy(text, button) {
    const status = button.parentElement.querySelector(".copy-status");
    navigator.clipboard.writeText(text).then(() => {
      if (status) {
        status.textContent = "Copied";
        setTimeout(() => (status.textContent = ""), 2000);
      } else {
        const original = button.textContent;
        button.textContent = "Copied";
        setTimeout(() => (button.textContent = original), 2000);
      }
    });
  }

  // Copy the structured script as labelled plain text
  document.querySelectorAll("[data-copy-script]").forEach((button) => {
    button.addEventListener("click", () => {
      const card = document.querySelector("[data-copy-source]");
      const text = Array.from(card.querySelectorAll("[data-part]"))
        .map((el) => {
          const label = el.dataset.part.toUpperCase();
          if (el.tagName === "UL") {
            return label + ":\n" + Array.from(el.children).map((li) => "- " + li.textContent.trim()).join("\n");
          }
          return label + ": " + el.textContent.trim();
        })
        .join("\n");
      copy(text, button);
    });
  });

  // Copy the nearest preformatted block
  document.querySelectorAll("[data-copy-raw]").forEach((button) => {
    button.addEventListener("click", () => {
      const scope = button.closest("details, section") || document;
      const pre = scope.querySelector("[data-copy-text]");
      if (pre) copy(pre.textContent, button);
    });
  });
})();
