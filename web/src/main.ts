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
    const lab = document.createElement("a");
    lab.className = "card";
    lab.href = "./lab.html";
    lab.innerHTML = `<h2>Mission Lab</h2><p>Write your own scenario in real Basilisk Python and fly it in an isolated sandbox.</p><span class="kind">edit &amp; run</span>`;
    container.appendChild(lab);
    const wasm = document.createElement("a");
    wasm.className = "card";
    wasm.href = "./wasm.html";
    wasm.innerHTML = `<h2>WASM Lab</h2><p>Basilisk compiled to WebAssembly — write and fly missions entirely inside your browser, no servers at all.</p><span class="kind">runs in your browser</span>`;
    container.appendChild(wasm);
  } catch (err) {
    container.innerHTML = `<div class="error-banner">Mission data failed to load: ${String(err)}</div>`;
  }
}

boot();
