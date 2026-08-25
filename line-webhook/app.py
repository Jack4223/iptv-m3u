#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
部署到 Render 的 LINE webhook 接收器（穩定版）：

  - LINE 設定 webhook 時會發 GET 驗證 -> 回 200 OK
  - 群組/好友發話 -> LINE POST 事件 -> 從 source 抓 groupId / userId
  - 抓到的 ID 會：
      1) 快取在本地 ids.json（Render 重啟會清掉，僅當暫存）
      2) 同時寫回 GitHub 倉庫 line-webhook/ids.json（永久保存，跨重啟不丟失）

  - 首頁 / 顯示目前已抓到的所有 ID（從 GitHub 讀回，渲染成 JSON）

部署：
  - Render Web Service，Runtime = Python 3
  - Build: pip install -r requirements.txt   （注意：Render 若設了 Root Directory=line-webhook，
    不要在前綴重複寫 line-webhook/，Build 只寫 pip install -r requirements.txt）
  - Start: gunicorn app:app --bind 0.0.0.0:$PORT
  - 環境變數：GITHUB_TOKEN = 你的 fine-grained PAT（範圍含本 repo 讀寫）
"""
import os, json, base64, datetime
from flask import Flask, request, jsonify
import requests

BASE = os.path.dirname(os.path.abspath(__file__))
IDS_FILE = os.path.join(BASE, "ids.json")

# GitHub 設定（寫回的位置）
REPO = "Jack4223/iptv-m3u"
BRANCH = "main"
GH_PATH = "line-webhook/ids.json"

PORT = int(os.environ.get("PORT", 10000))
# Render 的環境變數 GITHUB_TOKEN；若沒設，嘗試從同 repo 的 .github_token 讀（部署時可掛）
TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""

app = Flask(__name__)


def _gh_headers():
    return {
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/vnd.github+json",
    }


def load_ids_local():
    if os.path.exists(IDS_FILE):
        try:
            return json.load(open(IDS_FILE, encoding="utf-8"))
        except Exception:
            pass
    return {"group_ids": [], "user_ids": []}


def load_ids_github():
    """從 GitHub 讀回已保存的 ids.json（跨 Render 重啟也不丟）"""
    if not TOKEN:
        return None
    url = f"https://api.github.com/repos/{REPO}/contents/{GH_PATH}"
    try:
        r = requests.get(url, headers=_gh_headers(), params={"ref": BRANCH}, timeout=20)
        if r.status_code == 200:
            content = base64.b64decode(r.json()["content"]).decode("utf-8")
            return json.loads(content)
    except Exception:
        pass
    return None


def save_ids(ids):
    """本地快取 + 寫回 GitHub"""
    # 1) 本地快取
    try:
        json.dump(ids, open(IDS_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    except Exception:
        pass
    # 2) 寫回 GitHub
    if not TOKEN:
        return
    url = f"https://api.github.com/repos/{REPO}/contents/{GH_PATH}"
    sha = None
    try:
        r = requests.get(url, headers=_gh_headers(), params={"ref": BRANCH}, timeout=20)
        if r.status_code == 200:
            sha = r.json().get("sha")
    except Exception:
        pass
    content_b64 = base64.b64encode(
        json.dumps(ids, ensure_ascii=False, indent=2).encode("utf-8")
    ).decode("ascii")
    body = {
        "message": f"line-webhook: update ids {datetime.datetime.now().isoformat()}",
        "content": content_b64,
        "branch": BRANCH,
    }
    if sha:
        body["sha"] = sha
    try:
        requests.put(url, headers=_gh_headers(), json=body, timeout=20)
    except Exception:
        pass


def add_id(kind, val):
    # 優先以 GitHub 上的資料為準，避免本地/遠端不同步
    ids = load_ids_github() or load_ids_local()
    if kind not in ids:
        ids[kind] = []
    if val and val not in ids[kind]:
        ids[kind].append(val)
        save_ids(ids)
    return ids


@app.route("/", methods=["GET"])
def home():
    ids = load_ids_github() or load_ids_local()
    return jsonify({
        "status": "ok",
        "service": "line-webhook-id-collector",
        "group_ids": ids.get("group_ids", []),
        "user_ids": ids.get("user_ids", []),
    })


@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        return "OK", 200
    data = request.get_json(silent=True) or {}
    events = data.get("events", [])
    for e in events:
        src = e.get("source", {})
        if "groupId" in src:
            add_id("group_ids", src["groupId"])
        # 僅當「不在群組/聊天室」時才記錄為個人 user_id（避免把群組成員誤記）
        if "userId" in src and "groupId" not in src and "roomId" not in src:
            add_id("user_ids", src["userId"])
    return "OK", 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
