#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
部署到 Render 的 LINE webhook 接收器：
  - LINE 設定 webhook 時會發 GET 驗證 -> 回 200
  - 群組/好友發話 -> LINE POST 事件 -> 從 source 抓 groupId / userId 寫入 ids.json
  - 打開首頁 / 可看到目前已抓到的 ID（方便確認）
部署：pip install flask，Render 設 Web Service，Start command: python app.py
"""
import os, json
from flask import Flask, request, jsonify

BASE = os.path.dirname(os.path.abspath(__file__))
IDS_FILE = os.path.join(BASE, "ids.json")
PORT = int(os.environ.get("PORT", 8088))

app = Flask(__name__)

def load_ids():
    if os.path.exists(IDS_FILE):
        try:
            return json.load(open(IDS_FILE, encoding="utf-8"))
        except Exception:
            pass
    return {"group_ids": [], "user_ids": []}

def save_id(kind, val):
    d = load_ids()
    if val not in d[kind]:
        d[kind].append(val)
        json.dump(d, open(IDS_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    return d

@app.route("/", methods=["GET"])
def home():
    d = load_ids()
    return jsonify({"status": "ok", "group_ids": d["group_ids"], "user_ids": d["user_ids"]})

@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        return "OK", 200
    data = request.get_json(silent=True) or {}
    for e in data.get("events", []):
        src = e.get("source", {})
        if "groupId" in src:
            save_id("group_ids", src["groupId"])
        if "userId" in src and "groupId" not in src and "roomId" not in src:
            save_id("user_ids", src["userId"])
    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
