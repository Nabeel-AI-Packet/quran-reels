# Quran Reels agent: setup on your phone

You do this once, in about an hour. After that, everything happens in Telegram.

## How it works

- **07:00 every day:** the agent designs the day's Reel and sends it to you in Telegram.
- **You tap a button:** ✅ Post, 🔄 New design or ❌ Skip.
- **19:00:** approved Reels go live on Instagram, and the bot sends you the link.
- **Mondays:** the bot sends a weekly report.
- **Anytime:** send `/status` to the bot to see how many Reels are left.

## 1. GitHub (where the agent lives)

1. Open github.com in your phone's browser and create a free account.
2. Tap **+ → New repository**, name it `quran-reels`, choose **Public**, and tap **Create**.
3. Tell Claude the repository name. Claude uploads the code for you.

## 2. Telegram bot

1. In Telegram, open **@BotFather** and send `/newbot`.
2. Choose a name and a username ending in `bot`.
3. Copy the **token** BotFather sends you. It looks like `123456:ABC...`.

## 3. Instagram key

1. Switch your Instagram account to **Professional → Business**: Settings → Account type and tools.
2. Open developers.facebook.com, log in, and tap **Create app**.
3. Choose the use case **Manage messaging & content on Instagram**.
4. Under **API setup with Instagram login**, add your Instagram account and tap **Generate token**.
5. Copy the **access token** and your **Instagram user ID**, both shown on that screen.

## 4. GitHub key for renewing the Instagram key

1. On GitHub, go to Settings → Developer settings → Personal access tokens → **Fine-grained tokens** → Generate.
2. Under repository access, pick `quran-reels`. Under permissions, set **Secrets** to *Read and write*.
3. Copy the token.

## 5. Add the keys to GitHub

In your repository, go to **Settings → Secrets and variables → Actions → New repository secret**, and add:

| Name | Value |
| --- | --- |
| `TELEGRAM_TOKEN` | the BotFather token |
| `IG_TOKEN` | the Instagram access token |
| `IG_USER_ID` | the Instagram user ID |
| `GH_PAT` | the GitHub token from step 4 |

## 6. Connect yourself as the approver

1. Send any message to your new bot in Telegram.
2. On GitHub, open **Actions → poll → Run workflow**.
3. The bot replies with your **chat ID**. Add it as one more secret, `TELEGRAM_CHAT_ID`.

That's it. The first Reel arrives the next morning at 07:00. To get one right away, run **Actions → make-now → Run workflow**.

## Changing things

- **Page handle, posting time, reciter, hashtags:** edit `agent/config.py`, or ask Claude.
- **More Reels:** ask Claude for the next batch for `queue.json`.
- **Something broke:** the bot sends you the error. Forward it to Claude.
