# Quran Reels agent: setup on your phone

You do this once, in about 30 minutes. After that, everything happens in Telegram.

## How it works

- **Tuesday and Friday at 07:00:** the agent designs a Reel and sends it to you in Telegram.
- **You tap a button:** ✅ Post, 🔄 New design or ❌ Skip.
- **19:00:** approved Reels go live on Instagram automatically, and the bot sends you the link.
- **Anytime:** send `/status` to the bot to see how many Reels are left.

Posting runs through **Upload-Post** (upload-post.com), so you need no Meta developer account. The free plan allows 10 posts a month. For a Reel every day, take the Basic plan and set `POST_WEEKDAYS` in `agent/config.py` to every day.

## 1. Instagram

In the Instagram app, go to your profile → ☰ → **Account type and tools** → **Switch to professional account** → choose **Business**.

## 2. Upload-Post

1. Open upload-post.com and sign up for the free plan. No card is needed.
2. In the dashboard, create a **profile** (open Manage Users) and give it a short name, for example `quranreels`. Write that name down.
3. In that profile, connect **Instagram** and log in to your page.
4. Open the **API keys** page, create a key and copy it.

## 3. Telegram bot

1. In Telegram, open **@BotFather** and send `/newbot`.
2. Choose a name and a username ending in `bot`.
3. Copy the **token** BotFather sends you.

## 4. Add the keys to GitHub

Open github.com/Nabeel-AI-Packet/quran-reels in your browser with **Desktop site** turned on.
Go to **Settings → Secrets and variables → Actions → New repository secret** and add:

| Name | Value |
| --- | --- |
| `TELEGRAM_TOKEN` | the BotFather token |
| `UPLOADPOST_API_KEY` | the Upload-Post API key |
| `UPLOADPOST_USER` | the Upload-Post profile name, for example `quranreels` |

## 5. Connect yourself as the approver

1. In Telegram, open your bot and tap **Start**.
2. On GitHub, open the **Actions** tab. If it asks, tap **I understand my workflows, go ahead and enable them**.
3. Pick **poll** → **Run workflow** → **Run workflow**.
4. Within about 3 minutes the bot replies with your **chat ID**. Add it as one more secret, `TELEGRAM_CHAT_ID`.

## 6. Test

On GitHub, run **Actions → make-now → Run workflow**. Within about 5 minutes the first Reel arrives in Telegram. Tap ✅ Post and it goes live at 19:00.

## Changing things

- **Page handle, days, posting time, hashtags:** edit `agent/config.py`, or ask Claude.
- **More Reels:** ask Claude for the next batch for `queue.json`.
- **Something broke:** the bot sends you the error. Forward it to Claude.
