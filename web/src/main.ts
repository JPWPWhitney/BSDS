import "./style.css";

interface IndexEntry {
  id: string;
  title: string;
  kind: string;
  description: string;
}

async function boot() {
  const container = document.getElementById("scenario-cards")!;
  try {
    const res = await fetch("./data/index.json");
    if (!res.ok) throw new Error(`index.json: HTTP ${res.status}`);
    const index = (await res.json()) as { scenarios: IndexEntry[] };
    container.innerHTML = "";
    container.removeAttribute("aria-busy");
    for (const s of index.scenarios) {
      const a = document.createElement("a");
      a.className = "card";
      a.href = `./player.html?scenario=${encodeURIComponent(s.id)}`;
      const kindLabel = s.kind === "sweep" ? "interactive sweep" : "mission replay";
      a.innerHTML = `<h2></h2><p></p><span class="kind">${kindLabel}</span>`;
      a.querySelector("h2")!.textContent = s.title;
      a.querySelector("p")!.textContent = s.description;
      container.appendChild(a);
    }
  } catch (err) {
    container.innerHTML = `<div class="error-banner">Mission data failed to load: ${String(err)}</div>`;
  }
}

boot();
