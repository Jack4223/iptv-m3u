# iptv-m3u

台灣電視頻道播放清單（IPTV），精選「已實測可播」的台灣頻道。

## 檔案說明

| 檔案 | 內容 |
|------|------|
| `Taiwan.m3u` | 主清單：**39 個已實測可播**的台灣頻道（26 個 HLS 串流 + 13 個 YouTube 直播）。用影視倉等 App 直接匯入即可。 |

## 頻道來源

| 來源 | 數量 | 類型 |
|------|------|------|
| [iptv-org/iptv](https://github.com/iptv-org/iptv) | 26 | HLS 串流 |
| [Free-TV/IPTV](https://github.com/Free-TV/IPTV) | 13 | YouTube 直播 |

## 電視盒匯入步驟（以 Hako Mini + 影視倉為例）

1. 把 `Taiwan.m3u` 複製到 **USB 隨身碟**（根目錄即可）。
2. 隨身碟插進電視盒的 USB 口。
3. 打開**影視倉** App → 設定 / 直播配置 / 匯入 → 選**本地檔案** → 點 `Taiwan.m3u`。
4. 匯入完成後，直播列表就會出現頻道。

> 若影視倉讀不到隨身碟的檔案，試把 `.m3u` 放到盒子的 `Download/` 或 `Movies/` 資料夾。

## 更新方式

清單由 Hermes Agent 自動產生（測試每個頻道是否存活、去重）：

- 來源：iptv-org/tw + Free-TV/IPTV
- 測試：HTTP HEAD/GET 請求確認串流存活
- 產出：`Taiwan.m3u` → 上傳 GitHub

## 免責聲明

本倉庫僅收錄公開串流連結，不涉及任何內容託管。請依所在區域法規合理使用。
