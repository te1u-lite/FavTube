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

async function fetchVideoInfo(videoId: string){
    const res = await fetch(`http://localhost:8080/videos/${videoId}`);
    if(!res.ok) return null;
    return await res.json();
}

async function fetchAllTags(): Promise<string[]>{
    const res = await fetch(`http://localhost:8080/tags/all`);
    if(!res.ok)return [];
    return await res.json();
}

async function ensureVideoExists(VideoId: string, url:string){
    const res = await fetch("http://localhost:8080/videos/add-url",{
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({url}),
    });
    if (!res.ok)console.warn("Video registration failed:", await res.text());
}

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  (async () => {
    try {
      // --- 動画情報取得 ---
      if (msg.type === "get-video-info") {
        const id = msg.id;
        let video: any = null;
        try {
          const res = await fetch(`http://localhost:8080/videos/${id}`);
          if (res.ok) {
            video = await res.json();
          }
        } catch (e) {
          console.warn("動画取得エラー:", e);
        }

        // タグ一覧（404でも動作）
        let tags: string[] = [];
        try {
          const res2 = await fetch(`http://localhost:8080/tags/all`);
          if (res2.ok) tags = await res2.json();
        } catch (e) {
          console.warn("タグ取得エラー:", e);
        }

        sendResponse({ video, tags });
        return;
      }

      // --- 評価登録 ---
      if (msg.type === "rate") {
        const videoId = msg.id;
        const url = `https://www.youtube.com/watch?v=${videoId}`;

        // 存在しなければ登録してから評価
        await fetch("http://localhost:8080/videos/add-url", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ url }),
        });

        const res = await fetch(`http://localhost:8080/videos/${videoId}/rating`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ rating: msg.rating }),
        });

        let payload: any = null;
        try {payload = await res.json(); }catch {}
        sendResponse({ ok: res.ok, title: payload?.title || null});

        return;
      }

      // --- タグ追加 ---
      if (msg.type === "tag-add") {
        const videoId = msg.id;
        const tags = msg.tags;
        await fetch("http://localhost:8080/videos/add-url", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ url: `https://www.youtube.com/watch?v=${videoId}` }),
        });
        const res = await fetch(`http://localhost:8080/videos/${videoId}/tags`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ tags }),
        });
        sendResponse({ ok: res.ok });
        return;
      }

      // --- 未対応 ---
      sendResponse({ ok: false, error: "unknown message type" });
    } catch (e) {
      console.error("background.ts error:", e);
      sendResponse({ ok: false, error: String(e) });
    }
  })();

  return true; // これを忘れると UI が固まる
});
