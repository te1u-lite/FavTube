const API_BASE = "http://localhost:8080";

async function api(path: string, init?: RequestInit) {
  const r = await fetch(`${API_BASE}${path}`, {
    method: "GET",                          // 既定はGET
    ...(init || {}),                        // ← ★ これで method: "POST" などを上書き
    headers: {
      "Content-Type": "application/json",   // ← ★ 正しいヘッダ名
      ...(init?.headers || {}),
    },
  });
  const text = await r.text();
  if (!r.ok) throw new Error(`${r.status} ${text}`);
  try { return JSON.parse(text); } catch { return {}; }
}

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  (async () => {
    try {
      if (msg.type === "add-url") {
        await api("/videos/add-url", {
          method: "POST",
          body: JSON.stringify({ url: msg.url })
        });
      }
      if (msg.type === "rate") {
        await api(`/videos/${msg.id}/rating`, {
          method: "POST",
          body: JSON.stringify({ rating: msg.rating })
        });
      }
      if (msg.type === "tag-add") {
        const tags = String(msg.tags).split(",").map((t: string) => t.trim()).filter(Boolean);
        if (tags.length) {
          await api(`/videos/${msg.id}/tags`, {
            method: "POST",
            body: JSON.stringify({ tags })
          });
        }
      }
      sendResponse({ ok: true });
    } catch (e) {
      console.error(e);
      sendResponse({ ok: false, error: String(e) });
    }
  })();
  return true;
});
