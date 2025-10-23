// extension/src/content.ts
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

function toast(msg: string) {
  const t = document.createElement("div");
  Object.assign(t.style, {
    position: "fixed", right: "16px", bottom: "80px",
    background: "#333", color: "#fff", padding: "8px 12px",
    borderRadius: "8px", fontSize: "12px", zIndex: "2147483647",
    opacity: "0.95"
  });
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(()=> t.remove(), 2200);
}

function injectMiniUI(videoId: string) {
  // 重複生成を避ける
  if (document.getElementById("favtube-mini")) return;

  const root = document.createElement("div");
  root.id = "favtube-mini";
  Object.assign(root.style, {
    position: "fixed", right: "16px", bottom: "16px",
    background: "#fff", padding: "10px 12px", borderRadius: "12px",
    boxShadow: "0 8px 24px rgba(0,0,0,.25)", zIndex: "2147483647",
    display: "flex", gap: "8px", alignItems: "center", fontFamily: "system-ui"
  });

  const regBtn = document.createElement("button");
  regBtn.textContent = "登録";
  regBtn.onclick = () => {
    chrome.runtime.sendMessage({ type: "add-url", url: location.href }, (res) => {
      toast(res?.ok ? "登録しました" : `登録失敗: ${res?.error || ""}`);
    });
  };

  const starsWrap = document.createElement("div");
  for (let s = 1; s <= 5; s++) {
    const b = document.createElement("button");
    b.textContent = "☆";
    b.style.fontSize = "18px";
    b.title = `★${s}`;
    b.onclick = () => {
      chrome.runtime.sendMessage({ type: "rate", id: videoId, rating: s }, (res) => {
      toast(res?.ok ? `★${s} を保存` : `★保存失敗: ${res?.error || ""}`);
      });
    };
    starsWrap.appendChild(b);
  }

  const input = document.createElement("input");
  input.placeholder = "タグ(,区切り) Enterで送信";
  input.style.minWidth = "180px";
  input.onkeydown = (e) => {
    if ((e as KeyboardEvent).key === "Enter") {
      const tags = (e.target as HTMLInputElement).value.trim();
      if (!tags) return;
      chrome.runtime.sendMessage({ type: "tag-add", id: videoId, tags }, (res) => {
      toast(res?.ok ? "タグ追加" : `タグ追加失敗: ${res?.error || ""}`);
      });
      (e.target as HTMLInputElement).value = "";
    }
  };

  root.appendChild(regBtn);
  root.appendChild(starsWrap);
  root.appendChild(input);
  document.body.appendChild(root);
}

(function main() {
  // 初回
  const id = parseVideoIdFromUrl(location.href);
  if (id) injectMiniUI(id);

  // SPA遷移（YouTubeはURLだけ変わることがある）に簡易追従
  let last = location.href;
  const iv = setInterval(() => {
    if (last !== location.href) {
      last = location.href;
      const nid = parseVideoIdFromUrl(location.href);
      const old = document.getElementById("favtube-mini");
      if (old) old.remove();
      if (nid) injectMiniUI(nid);
    }
  }, 1000);

  // ページ離脱時に監視停止
  window.addEventListener("beforeunload", () => clearInterval(iv));
})();
