# Quran Reels agent: setup on your phone

You do this once, in about 30 minutes. After that, everything happens in Telegram.

## How it works

- **Tuesday and Friday at 07:00:** the agent designs a Reel and sends it to you in Telegram.
- **You tap a button:** ✅ Post at 19:00, 🚀 Post now, 🔄 New design or ❌ Skip.
- **19:00:** approved Reels go live on Instagram, TikTok and X automatically, and the bot sends you the links.
- **🚀 Post now** under a Reel posts it right away instead of at 19:00. Already tapped ✅? Send `/postnow`.
- **Your own posts:** send the bot any video or photo (up to 20 MB, caption included) and tap 📤 to post it. Nothing is posted without that tap.
- **Anytime:** send `/status` to the bot to see how many Reels are left.

Posting runs through **Buffer** (buffer.com, free plan), so you need no Meta, TikTok or X developer account. Buffer finds your connected accounts by itself: there are no IDs to copy. Keep this repository **public**: Buffer downloads each approved video from it, and public repositories get unlimited free GitHub Actions time.

## 1. Instagram

In the Instagram app, go to your profile → ☰ → **Account type and tools** → **Switch to professional account** → choose **Business**.

## 2. Buffer (Instagram, TikTok, X)

1. Open buffer.com and sign up for the **Free** plan. No card is needed.
2. Connect your **Instagram**, **TikTok** and **X** accounts (Buffer → Channels → Connect) and log in to each. Leave out any you don't want; the agent skips them.
3. Open developers.buffer.com while logged in → **Get API Key** → create a key and copy it.

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
| `BUFFER_API_KEY` | the Buffer API key |

## 5. Connect yourself as the approver

1. In Telegram, open your bot and tap **Start**.
2. On GitHub, open the **Actions** tab. If it asks, tap **I understand my workflows, go ahead and enable them**.
3. Pick **poll** → **Run workflow** → **Run workflow**.
4. Within about 3 minutes the bot replies with your **chat ID**. Add it as one more secret, `TELEGRAM_CHAT_ID`.

## 6. Test

Send `/status` to the bot: the last line shows **Posting via: Buffer →** and the accounts it found. Then run **Actions → make-now → Run workflow** on GitHub. Within about 5 minutes the first Reel arrives in Telegram. Tap ✅ Post and it goes live at 19:00 on every connected platform.

## Changing things

- **Page handle, days, posting time, hashtags:** edit `agent/config.py`, or ask Claude.
- **More Reels:** ask Claude for the next batch for `queue.json`.
- **Something broke:** the bot sends you the error. Forward it to Claude.

## If you already set up Upload-Post

It keeps working until you add `BUFFER_API_KEY`; from then on Buffer is used. You can delete the two `UPLOADPOST_` secrets afterwards.
