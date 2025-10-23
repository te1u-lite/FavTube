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

function extractId(url: string):string{
    try{
        const u = new URL(url);
        if (u.hostname ==="youtu.be") return u.pathname.slice(1);
        if(u.pathname.startsWith("/shorts/")) return u.pathname.split("/")[2];
        return u.searchParams.get("v") || "";
    }catch {return "";}
}

const inflight = new Map<string, Promise<any>>();

function ensureRegisteredByUrl(url: string):Promise<any>{
    const vid = extractId(url);
    if(!vid) return Promise.reject(new Error("invalid url"));
    return ensureRegistered(vid,() =>
    api("/videos/add-url", {method: "POST",body: JSON.stringify({url}) })
    );
}

function ensureRegisteredById(id: string): Promise<any>{
    return ensureRegistered(id, () =>
    api("/videos", {method: "POST", body: JSON.stringify({id})})
    );
}

function ensureRegistered(id: string, registerFn: () => Promise<any>): Promise<any>{
    const existed = inflight.get(id);
    if (existed) return existed;    // すでに登録中ならそれを使う
    const p = (async ()=>{
        try{
            await registerFn();
        }finally{
            inflight.delete(id);
        }
    })();
    inflight.set(id, p);
    return p;
}

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  (async () => {
    try {
      if (msg.type === "add-url") {
        await ensureRegisteredByUrl(msg.url);
      }

      if (msg.type === "rate") {
        await ensureRegisteredById(msg.id);
        await api(`/videos/${msg.id}/rating`,{
            method: "POST",
            body: JSON.stringify({ rating: msg.rating})
        });
      }

      if (msg.type === "tag-add") {
        await ensureRegisteredById(msg.id);
        const tags = String(msg.tags)
            .split(/[,\u3001\uFF0C]/)
            .map((t: string) => t.trim())
            .filter(Boolean);
        if(tags.length){
            await api(`/videos/${msg.id}/tags`, {
                method: "POST",
                body: JSON.stringify({ tags})
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
