document.querySelectorAll("form[data-confirm]").forEach((form) => {
  form.addEventListener("submit", (event) => {
    if (!window.confirm(form.dataset.confirm)) {
      event.preventDefault();
    }
  });
});

const quantity = document.querySelector("#quantity");
if (quantity) {
  document.querySelectorAll("[data-step]").forEach((button) => {
    button.addEventListener("click", () => {
      const current = quantity.valueAsNumber || 1;
      const next = current + Number(button.dataset.step);
      quantity.value = Math.max(1, Math.min(Number(quantity.max), next));
    });
  });
}
