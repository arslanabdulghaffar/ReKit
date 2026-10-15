"use strict";
// Select already rendered, recorded results. No fetch, storage or mutation API.
for (const button of document.querySelectorAll("#labor-controls button[data-rate]")) {
  button.addEventListener("click", () => {
    const rate = button.dataset.rate;
    for (const item of document.querySelectorAll("#labor-controls button[data-rate]")) {
      item.setAttribute("aria-pressed", String(item === button));
    }
    for (const panel of document.querySelectorAll(".rate-panel")) {
      panel.hidden = panel.id !== `rate-panel-${rate}`;
    }
    document.getElementById("comparison-status").textContent =
      `Showing recorded results at $${(Number(rate) / 100).toFixed(2)} per minute.`;
  });
}
