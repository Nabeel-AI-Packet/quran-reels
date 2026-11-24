"""Settings you may want to change. Keys and tokens live in GitHub secrets, never here."""
import os

PAGE_HANDLE = "@yourpage"                 # shown at the end of every Reel

# Reciters on everyayah.com: display name -> folder name on the site.
RECITERS = {
    "Yasser Al-Dosari": "Yasser_Ad-Dussary_128kbps",
    # "Hasan Al-Adani": "<folder name from everyayah.com>",
}
DEFAULT_RECITER = "Yasser Al-Dosari"

# Verse text: Uthmani Arabic, Saheeh International (English), Jozef Bielawski (Polish).
EDITIONS = ("quran-uthmani", "en.sahih", "pl.bielawskiego")
TRANSLATION_CREDIT = "Saheeh International (EN), J. Bielawski (PL)"

# When approved Reels go live, in your local time.
TIMEZONE = "Europe/Warsaw"
# Days a Reel is made: 0=Mon ... 6=Sun. Two a week fits Upload-Post's free plan
# (10 posts a month). On a paid plan, use (0, 1, 2, 3, 4, 5, 6) for every day.
POST_WEEKDAYS = (1, 4)                    # Tuesday and Friday
MAKE_HOUR = 7                             # the day's Reel arrives in Telegram from 07:00
POST_HOUR = 19                            # 19:00; approved earlier -> waits until then

HASHTAGS = "#quran #quranrecitation #islam #muslim #islamicreminders #dua #koran #islampolska"

# Who may approve: the Telegram chat ID of the approver (set as a GitHub secret).
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
# How Reels reach Instagram: "uploadpost" (Upload-Post service, no Meta app needed)
# or "meta" (your own Meta developer app).
POSTER = os.environ.get("POSTER") or "uploadpost"
UPLOADPOST_API_KEY = os.environ.get("UPLOADPOST_API_KEY", "")
UPLOADPOST_USER = os.environ.get("UPLOADPOST_USER", "")
IG_TOKEN = os.environ.get("IG_TOKEN", "")
IG_USER_ID = os.environ.get("IG_USER_ID", "")
REPO = os.environ.get("GITHUB_REPOSITORY", "")   # "user/repo", set by GitHub automatically
BRANCH = os.environ.get("GITHUB_REF_NAME", "main")
