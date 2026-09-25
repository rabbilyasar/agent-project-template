const form = document.getElementById("widget-form");
const list = document.getElementById("widget-list");

// Bug for bench/tasks/browser-ui.md: no disabled/loading state while the
// fetch is in flight.
form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const clientId = document.getElementById("client-id").value;
  const res = await fetch(`/widgets?clientId=${encodeURIComponent(clientId)}`);
  const widgets = await res.json();
  list.innerHTML = widgets.map((w) => `<li>${w.name}</li>`).join("");
});
