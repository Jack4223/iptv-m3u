#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
部署到 Render 的 LINE webhook 接收器（v2：本地+GitHub 雙寫，首頁顯示聯集）：

  - GET /            -> 顯示目前已抓到的 group_ids / user_ids
                        （聯集：GitHub 上的 + Render 本地的，任一处有就顯示）
  - GET /webhook     -> LINE 驗證回 OK
  - POST /webhook    -> 收 LINE 事件，抓 groupId / userId
                        1) 寫本地 ids.json（Render 本地，快取）
                        2) 嘗試寫回 GitHub（持久化，跨重啟不丟；失敗也不影響本地）

  這版不強依賴 GitHub 寫入成功：即使 GITHUB_TOKEN 在 Render 端讀不到，
  本地仍會存住 id，首頁讀本地就能看到，方便即時抓取 group_id。
"""
import os, json, base64, datetime
from flask import Flask, request, jsonify
import requests

BASE = os.path.dirname(os.path.abspath(__file__))
IDS_FILE = os.path.join(BASE, "ids.json")

REPO = "Jack4223/iptv-m3u"
BRANCH = "main"
GH_PATH = "line-webhook/ids.json"

PORT = int(os.environ.get("PORT", 10000))
TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""

app = Flask(__name__)

# 記憶體診斷（不依賴檔案系統，確保能看到 LINE 送來的原始事件）
LAST_EVENT = {"received": False}
WRITE_LOG = []


def _gh_headers():
    return {"Authorization": f"Bearer {TOKEN}", "Accept": "application/vnd.github+json"}


def load_local():
    if os.path.exists(IDS_FILE):
        try:
            return json.load(open(IDS_FILE, encoding="utf-8"))
        except Exception:
            pass
    return {"group_ids": [], "user_ids": []}


def load_github():
    if not TOKEN:
        return None
    try:
        r = requests.get(
            f"https://api.github.com/repos/{REPO}/contents/{GH_PATH}",
            headers=_gh_headers(), params={"ref": BRANCH}, timeout=20)
        if r.status_code == 200:
            return json.loads(base64.b64decode(r.json()["content"]).decode("utf-8"))
    except Exception:
        pass
    return None


def save_local(ids):
    try:
        json.dump(ids, open(IDS_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    except Exception:
        pass


def save_github(ids):
    if not TOKEN:
        return False
    url = f"https://api.github.com/repos/{REPO}/contents/{GH_PATH}"
    sha = None
    try:
        r = requests.get(url, headers=_gh_headers(), params={"ref": BRANCH}, timeout=20)
        if r.status_code == 200:
            sha = r.json().get("sha")
    except Exception:
        pass
    content_b64 = base64.b64encode(
        json.dumps(ids, ensure_ascii=False, indent=2).encode("utf-8")).decode("ascii")
    body = {"message": f"line-webhook: update {datetime.datetime.now().isoformat()}",
            "content": content_b64, "branch": BRANCH}
    if sha:
        body["sha"] = sha
    try:
        r = requests.put(url, headers=_gh_headers(), json=body, timeout=20)
        return r.status_code in (200, 201)
    except Exception:
        return False


def add_id(kind, val):
    if not val:
        return
    # 以 GitHub 為準合併，避免本地/遠端分歧
    gh = load_github() or {"group_ids": [], "user_ids": []}
    loc = load_local()
    merged = {"group_ids": list(set(gh.get("group_ids", []) + loc.get("group_ids", []))),
              "user_ids": list(set(gh.get("user_ids", []) + loc.get("user_ids", [])))}
    if kind not in merged:
        merged[kind] = []
    if val not in merged[kind]:
        merged[kind].append(val)
        save_local(merged)          # 本地一定存
        save_github(merged)         # GitHub 嘗試存（失敗也不影響）


@app.route("/", methods=["GET"])
def home():
    gh = load_github() or {"group_ids": [], "user_ids": []}
    loc = load_local()
    all_g = list(set(gh.get("group_ids", []) + loc.get("group_ids", [])))
    all_u = list(set(gh.get("user_ids", []) + loc.get("user_ids", [])))
    return jsonify({
        "status": "ok",
        "service": "line-webhook-id-collector-v3",
        "github_group_ids": gh.get("group_ids", []),
        "local_group_ids": loc.get("group_ids", []),
        "group_ids": all_g,
        "user_ids": all_u,
        "token_present": bool(TOKEN),
        "last_event_received": LAST_EVENT.get("received", False),
        "last_event_source": LAST_EVENT.get("source"),
        "last_event_type": LAST_EVENT.get("type"),
        "write_log": WRITE_LOG[-5:],
    })


@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        return "OK", 200
    data = request.get_json(silent=True) or {}
    # 記錄原始事件（記憶體，診斷用）
    events = data.get("events", [])
    if events:
        e0 = events[0]
        LAST_EVENT["received"] = True
        LAST_EVENT["type"] = e0.get("type")
        LAST_EVENT["source"] = e0.get("source", {})
    # ★ 關鍵：先立即回應 200（LINE 要求極快回應，否則判定逾時放棄），
    #   再用背景線程慢慢處理存檔，避免我們的處理拖慢回應導致 LINE 放棄推送。
    import threading
    def _process():
        for e in events:
            src = e.get("source", {})
            if "groupId" in src:
                add_id("group_ids", src["groupId"])
                WRITE_LOG.append(f"got group_id={src['groupId']}")
            elif "userId" in src and "roomId" not in src:
                add_id("user_ids", src["userId"])
                WRITE_LOG.append(f"got user_id={src['userId']}")
            else:
                WRITE_LOG.append(f"event no id: type={e.get('type')} src_keys={list(src.keys())}")
    threading.Thread(target=_process, daemon=True).start()
    return "OK", 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
