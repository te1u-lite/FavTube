// --- 小ユーティリティ ------------------------------------
function parseVideoIdFromUrl(href: string): string | null {
  try {
    const u = new URL(href);
    if (u.hostname === "youtu.be") {
      const vid = u.pathname.slice(1);
      return /^[A-Za-z0-9_-]{11}$/.test(vid) ? vid : null;
    }
    if (u.pathname.startsWith("/shorts/")) {
      const vid = u.pathname.split("/")[2];
      return /^[A-Za-z0-9_-]{11}$/.test(vid) ? vid : null;
    }
    const vid = u.searchParams.get("v");
    return vid && /^[A-Za-z0-9_-]{11}$/.test(vid) ? vid : null;
  } catch {
    return null;
  }
}

function ensureUIRoot(): HTMLElement {
  const old = document.getElementById("favtube-ui");
  if (old) old.remove();
  const root = document.createElement("div");
  root.id = "favtube-ui";
  Object.assign(root.style, {
    position: "fixed", right: "20px", bottom: "20px",
    width: "320px", background: "#0b0b0c", color: "#fff",
    borderRadius: "14px", padding: "14px",
    boxShadow: "0 8px 28px rgba(0,0,0,.55)",
    fontFamily: "Inter, system-ui, -apple-system, 'Segoe UI'", fontSize: "14px", zIndex: "2147483647",
    border: "1px solid #1f1f22"
  } as CSSStyleDeclaration);
  root.innerHTML = `
    <div id="fvt-title" style="font-weight:700;color:#e6e6e6;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">読み込み中...</div>
    <div style="display:flex;align-items:center;gap:8px;margin-top:8px">
      <span style="color:#9ca3af">★</span>
      <div id="fvt-stars" style="display:flex;gap:6px"></div>
    </div>
    <div style="margin-top:10px">
      <div style="color:#9ca3af">タグ</div>
      <div id="fvt-tags" style="display:flex;flex-wrap:wrap;gap:6px;margin-top:6px"></div>
      <input id="fvt-tag-input" placeholder="タグ追加..." 
             style="margin-top:6px;width:100%;background:#111214;color:#fff;padding:8px;border-radius:10px;border:1px solid #2a2a2e;outline:none"
      />
      <ul id="fvt-suggestions" style="margin-top:6px;max-height:120px;overflow:auto;background:#121317;border:1px solid #2a2a2e;border-radius:10px;display:none;padding:6px"></ul>
    </div>
  `;
  document.body.appendChild(root);
  return root;
}

function setTitle(text: string, registered: boolean){
  const el = document.getElementById("fvt-title")!;
  el.textContent =text;
  el.setAttribute("data-registered",registered ? "1": "0");
  el.style.color = registered ? "#e6e6e6" : "#f59e0b";
}


function toast(msg: string) {
  const t = document.createElement("div");
  Object.assign(t.style, {
    position:"fixed", right:"24px", bottom:"100px",
    background:"#18181b", color:"#fff", padding:"8px 12px",
    borderRadius:"10px", boxShadow:"0 6px 22px rgba(0,0,0,.5)", zIndex:"2147483647",
    border:"1px solid #2a2a2e", fontSize:"12px", opacity:"0.97"
  } as CSSStyleDeclaration);
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(()=> t.remove(), 2200);
}

// --- 状態 ---------------------------------------------------
type VideoState = { id: string; title?: string; rating?: number; tags?: string[]; registered: boolean };
let current: VideoState | null = null;
let allTags: string[] = [];

// --- 描画 ---------------------------------------------------
function renderStars(rating: number) {
  const el = document.getElementById("fvt-stars")!;
  el.innerHTML = "";
  for (let i = 1; i <= 5; i++) {
    const b = document.createElement("button");
    b.textContent = i <= rating ? "★" : "☆";
    b.style.fontSize = "20px";
    b.style.lineHeight = "1";
    b.style.cursor = "pointer";
    b.style.color = i <= rating ? "#facc15" : "#555b";
    b.title = `★${i}`;
    b.addEventListener("click", () => {
      if (!current) return;
      chrome.runtime.sendMessage(
        { type: "rate", id: current.id, rating: i },
        (res) => {
          if (res?.ok) {
            // バックエンドは rating 成功時に title を返す実装（あれば更新）
            if (res.title) {
              current!.title = res.title;   // ← タイトルを即反映（リアルタイム）
              current!.registered = true
              setTitle(res.title,true);
            }
            current!.rating = i;
            renderStars(i);                  // ← 星も即反映
            toast(`★${i} を保存しました`);
          } else {
            toast(`★保存失敗: ${res?.error || ""}`);
          }
        }
      );
    });
    el.appendChild(b);
  }
}

function renderTags(tags: string[]) {
  const el = document.getElementById("fvt-tags")!;
  el.innerHTML = "";
  tags.forEach(tag => {
    const pill = document.createElement("span");
    pill.textContent = tag;
    Object.assign(pill.style, {
      background:"#1b1c22", color:"#e5e7eb", padding:"4px 8px",
      borderRadius:"999px", fontSize:"12px", border:"1px solid #2a2a2e"
    } as CSSStyleDeclaration);
    el.appendChild(pill);
  });
}

function wireTagInput() {
  const input = document.getElementById("fvt-tag-input") as HTMLInputElement;
  const sug = document.getElementById("fvt-suggestions") as HTMLUListElement;

  input.oninput = () => {
    const q = input.value.trim().toLowerCase();
    if (!q) { sug.style.display = "none"; return; }
    const matched = allTags.filter(t => t.toLowerCase().includes(q)).slice(0, 8);
    sug.innerHTML = matched.map(m => `<li data-tag="${m}" style="padding:6px;border-radius:8px;cursor:pointer;color:#e5e7eb">${m}</li>`).join("");
    matched.length ? (sug.style.display = "block") : (sug.style.display = "none");
    Array.from(sug.querySelectorAll("li")).forEach(li => {
      li.addEventListener("mouseenter", () => (li as HTMLElement).style.background = "#1e1f26");
      li.addEventListener("mouseleave", () => (li as HTMLElement).style.background = "transparent");
      li.addEventListener("click", () => {
        input.value = (li as HTMLElement).dataset.tag || "";
        sug.style.display = "none";
        input.focus();
      });
    });
  };

  input.onkeydown = (e) => {
    if (e.key === "Enter" && input.value.trim() && current) {
      const tag = input.value.trim();
      chrome.runtime.sendMessage(
        { type: "tag-add", id: current.id, tags: [tag] },
        (res) => {
          if (res?.ok) {
            const next = Array.from(document.querySelectorAll<HTMLSpanElement>("#fvt-tags span"))
              .map(s => s.textContent || "")
              .filter(Boolean)
              .concat(tag);
            current!.tags = next;
            renderTags(next);       // ← 即時反映
            input.value = "";
            toast(`タグ '${tag}' を追加しました`);
          } else {
            toast(`タグ追加失敗: ${res?.error || ""}`);
          }
        }
      );
    }
  };
}

// --- 初期化 & データ取得 ------------------------------------
function renderInitial(id: string) {
  ensureUIRoot();
  const titleEl = document.getElementById("fvt-title")!;
  titleEl.textContent = "読み込み中...";
  renderStars(0);
  renderTags([]);
  wireTagInput();

  chrome.runtime.sendMessage({ type: "get-video-info", id }, (res) => {
    const titleEl = document.getElementById("fvt-title")!;
    if (!res) {
      titleEl.textContent = "通信エラー";
      return;
    }
    if (res.video) {
      current = {
        id,
        title: res.video.title,
        rating: res.video.rating || 0,
        tags: res.video.tags || [],
        registered: true,
      };
      setTitle(current.title || "(タイトル不明",true);
      renderStars(current.rating || 0);
      renderTags(current.tags || []);
    } else {
      current = { id, registered: false, rating: 0, tags: [] };
      setTitle("未登録",false);
      renderStars(0);
      renderTags([]);
    }
    allTags = res.tags || [];
  });

}

function boot() {
  const id = parseVideoIdFromUrl(location.href);
  if (!id) return;
  renderInitial(id);

  // YouTubeのSPA遷移に追従
  let last = location.href;
  const iv = setInterval(() => {
    if (last !== location.href) {
      last = location.href;
      const nid = parseVideoIdFromUrl(location.href);
      if (!nid) return;
      renderInitial(nid);
    }
  }, 800);
  window.addEventListener("beforeunload", () => clearInterval(iv));
}

boot();
