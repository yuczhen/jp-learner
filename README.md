# jp-learner — 日檢 N5~N3 每日單字＋文法（Telegram＋網頁）

個人日檢備考工具：每天早 08:00／晚 18:00（台灣時間）自動推送一批「相近文法一組＋搭配單字」到 Telegram，
完整內容（全部單字、例句、🔊發音、已熟悉勾選）在網頁。

## 功能
- **每日兩班**（早 08:00／晚 18:00，台灣時間）：每批＝一組相近文法＋搭配單字；早班淺色（橘 🟠）、晚班星空（藍 🔵），Telegram 與網頁都以顏色區分。
- **每個單字都有例句**（N5~N3 程度，漢字／片假名皆附平假名注音與中文翻譯）。
- **相似文法對照表**（26 組、含記憶口訣）：每批相關對照自動出現，另有「📊 對照表」總覽頁可搜尋。
- **課堂講義整合**與**敬語**專區（動詞對照表、尊敬／謙讓／丁寧）。
- **預先合成的日文語音**（單字、例句、文法例句）：奇數天女聲、偶數天男聲，同一天固定同一人；語音包與內容一起加密，網頁按需解密播放，失敗時退回瀏覽器語音。
- 「已熟悉」勾選、隱藏已熟悉（存在瀏覽器本機）。

## 設計
- 約 2,500 單字＋244 文法，排成 72 批（36 天學新、其後複習，考前一週自由複習）。
- 相近句型放同一批（理由／對比／逆接／推測／假定…）；單字優先挑出現在該批文法例句中的字，其餘依級別對齊進度。
- Telegram 只發精簡摘要（文法＋接續＋例句＋10 個精選單字＋日文語音 mp3），完整清單在網頁。
- **學習內容不公開**：資料以 AES-256-GCM 加密成 `docs/data/bundle.enc` 才上傳，網頁開啟時輸入密碼於瀏覽器內解密；
  資料準備腳本與原始資料僅存在本機（見 `.gitignore`）。

## 結構
```
scripts/build_plan.py      # 產生學習計畫（讀本機資料）
scripts/tts_text.py        # 語音朗讀文字規則（一律用假名，避免讀錯漢字）
scripts/crypto_bundle.py   # 加密／解密資料包
scripts/notify.py          # Telegram 推送（Actions 內以 secret 解密）
docs/index.html            # 網頁（GitHub Pages，從 /docs 發布）
.github/workflows/daily.yml
```

## 環境變數（寫在本機 `.env` 與 GitHub Secrets，**不入版控**）
| 名稱 | 用途 |
|---|---|
| `DATA_PASSWORD` | 加解密資料包 |
| `TG_TOKEN`、`TG_CHAT_ID` | Telegram bot |
| `SITE_URL` | 網頁網址（訊息內連結，可留空） |

## 語音包（本機產生，加密後才上傳）
```bash
set -a; . ./.env; set +a
.venv/bin/python scripts/gen_audio.py          # 合成（edge-tts）→ 壓縮 → 依批次加密 → docs/data/a/*.enc
.venv/bin/python scripts/crypto_bundle.py      # 重新加密主資料包（含語音索引）
```

## 更新資料
```bash
set -a; . ./.env; set +a
.venv/bin/python scripts/build_plan.py
.venv/bin/python scripts/crypto_bundle.py      # 重新加密 → docs/data/bundle.enc
.venv/bin/python scripts/notify.py --slot am --date 2026-10-16 --dry-run   # 預覽訊息
```

## 設定排程
1. @BotFather 建立 bot；傳一句話給 bot 後以 `getUpdates` 取得 chat id。
2. Repo → Settings → Secrets and variables → Actions：新增上表四個 Secrets。
3. Settings → Pages：Source 選 `main` / `/docs`。
4. Actions → daily-telegram → Run workflow 手動測試一次。
