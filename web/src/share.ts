/** DOM wiring shared by both lab pages: share links, URL loading, file upload.
 * All decodable logic lives in sharecore.ts. */

import type { EditorView } from "codemirror";

import {
  buildShareUrl,
  decodeShareCode,
  encodeShareCode,
  gistApiUrl,
  parseLoadRequest,
  pickGistFile,
  SHARE_WARN_LENGTH,
  type LoadRequest,
} from "./sharecore";

export interface ShareHooks {
  editor: EditorView;
  select: HTMLSelectElement;
  showMessage(text: string): void;
}

export function setEditorCode(editor: EditorView, code: string): void {
  editor.dispatch({ changes: { from: 0, to: editor.state.doc.length, insert: code } });
}

/** Show in the template picker that the editor holds code from elsewhere. */
function markExternalSource(select: HTMLSelectElement, label: string): void {
  let opt = select.querySelector<HTMLOptionElement>("option[data-external]");
  if (!opt) {
    opt = document.createElement("option");
    opt.dataset.external = "1";
    opt.disabled = true;
    select.prepend(opt);
  }
  opt.textContent = label;
  opt.selected = true;
}

async function fetchText(url: string, what: string): Promise<string> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`HTTP ${res.status} fetching ${what}`);
  return res.text();
}

async function resolveLoadRequest(req: LoadRequest): Promise<string> {
  switch (req.kind) {
    case "code":
      return decodeShareCode(req.payload);
    case "src":
      return fetchText(req.url, "the linked file");
    case "gist": {
      const res = await fetch(gistApiUrl(req.id));
      if (!res.ok) throw new Error(`HTTP ${res.status} from the gist API`);
      const pick = pickGistFile(await res.json());
      if (!pick) throw new Error("the gist has no loadable file");
      return "content" in pick ? pick.content : fetchText(pick.rawUrl, "the gist file");
    }
  }
}

function sourceLabel(req: LoadRequest): string {
  if (req.kind === "code") return "shared code";
  if (req.kind === "gist") return `gist ${req.id}`;
  return req.url.split(/[?#]/)[0].split("/").pop() || "linked file";
}

function describeLoadFailure(req: LoadRequest): string {
  if (req.kind === "code") return "This share link couldn't be decoded — it may have been cut short when copied.";
  if (req.kind === "gist") return `Couldn't load gist ${req.id}.`;
  return `Couldn't load the scenario from ${req.url}.`;
}

/** Honor `#code=` / `?src=` / `?gist=` in the page URL. True when the editor
 * was filled; false (with a message on failure) means load the default. */
export async function loadFromUrl(hooks: ShareHooks): Promise<boolean> {
  const req = parseLoadRequest(location.hash, location.search);
  if (!req) return false;
  try {
    setEditorCode(hooks.editor, await resolveLoadRequest(req));
    markExternalSource(hooks.select, sourceLabel(req));
    return true;
  } catch (err) {
    hooks.showMessage(
      `${describeLoadFailure(req)}\n(${String(err)})\nStarting with the default template instead.`,
    );
    return false;
  }
}

/** Wire the Share button and the Open .py button + hidden file input. */
export function initShareControls(hooks: ShareHooks): void {
  const shareBtn = document.getElementById("share-btn") as HTMLButtonElement;
  const openBtn = document.getElementById("open-btn") as HTMLButtonElement;
  const fileInput = document.getElementById("file-input") as HTMLInputElement;

  shareBtn.addEventListener("click", async () => {
    const encoded = await encodeShareCode(hooks.editor.state.doc.toString());
    const url = buildShareUrl(location.href, encoded);
    history.replaceState(null, "", url);
    let copied = false;
    try {
      await navigator.clipboard.writeText(url);
      copied = true;
    } catch {
      // clipboard unavailable or denied — the link below is the fallback
    }
    const lines = [
      copied
        ? "Share link copied to your clipboard — anyone who opens it sees this exact code:"
        : "Clipboard unavailable — copy this share link by hand:",
      url,
    ];
    if (encoded.length > SHARE_WARN_LENGTH) {
      lines.push(
        `Heads up: this link is ${(url.length / 1024).toFixed(1)} KB — some chat apps truncate ` +
          `very long URLs. If it misbehaves, share the .py file itself instead.`,
      );
    }
    hooks.showMessage(lines.join("\n"));
  });

  openBtn.addEventListener("click", () => fileInput.click());
  fileInput.addEventListener("change", async () => {
    const file = fileInput.files?.[0];
    if (!file) return;
    setEditorCode(hooks.editor, await file.text());
    markExternalSource(hooks.select, file.name);
    fileInput.value = "";
  });
}
