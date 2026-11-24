"""Settings you may want to change. Keys and tokens live in GitHub secrets, never here."""
import os

# Reciters on everyayah.com. Reels rotate through them in this order.
RECITERS = {
    "Yasser Al-Dosari": {"folder": "Yasser_Ad-Dussary_128kbps", "ar": "الشيخ ياسر الدوسري"},
    "Maher Al-Muaiqly": {"folder": "MaherAlMuaiqly128kbps", "ar": "الشيخ ماهر المعيقلي"},
    "Mishary Alafasy": {"folder": "Alafasy_128kbps", "ar": "الشيخ مشاري راشد العفاسي"},
    "Abdurrahman As-Sudais": {"folder": "Abdurrahmaan_As-Sudais_192kbps", "ar": "الشيخ عبد الرحمن السديس"},
}

# Verse text: Uthmani Arabic, Saheeh International (English), Jozef Bielawski (Polish).
EDITIONS = ("quran-uthmani", "en.sahih", "pl.bielawskiego")
TRANSLATION_CREDIT = "Saheeh International (EN), J. Bielawski (PL)"

# When approved Reels go live, in your local time.
TIMEZONE = "Europe/Warsaw"
# Where and on which days to post: 0=Mon ... 6=Sun. A Reel is made on every day
# listed for any platform. With Buffer (free) a Reel goes to every platform you connected
# in Buffer on these days; platforms you didn't connect are skipped automatically.
POST_DAYS = {
    "instagram": (1, 4),                  # Tuesday and Friday
    "tiktok": (1, 4),
    "x": (1, 4),
}
POST_WEEKDAYS = tuple(sorted({d for days in POST_DAYS.values() for d in days}))
MAKE_HOUR = 7                             # the day's Reel arrives in Telegram from 07:00
POST_HOUR = 19                            # 19:00; approved earlier -> waits until then

HASHTAGS = "#quran #quranrecitation #islam #muslim #islamicreminders #dua #koran #islampolska"

# Who may approve: the Telegram chat ID of the approver (set as a GitHub secret).
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
# How Reels are posted: "buffer" (Buffer, free: Instagram + TikTok + X, no developer apps),
# "uploadpost" (Upload-Post) or "meta" (your own Meta app). Chosen automatically: Buffer
# as soon as the BUFFER_API_KEY secret exists.
BUFFER_API_KEY = os.environ.get("BUFFER_API_KEY", "")
POSTER = os.environ.get("POSTER") or ("buffer" if BUFFER_API_KEY else "uploadpost")
UPLOADPOST_API_KEY = os.environ.get("UPLOADPOST_API_KEY", "")
UPLOADPOST_USER = os.environ.get("UPLOADPOST_USER", "")
IG_TOKEN = os.environ.get("IG_TOKEN", "")
IG_USER_ID = os.environ.get("IG_USER_ID", "")
REPO = os.environ.get("GITHUB_REPOSITORY", "")   # "user/repo", set by GitHub automatically
BRANCH = os.environ.get("GITHUB_REF_NAME", "main")
