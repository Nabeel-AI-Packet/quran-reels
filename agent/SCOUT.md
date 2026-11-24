# Video scout (run by a Claude scheduled task every morning)

Goal: suggest 5 inspiring short Quran recitation videos to the owner, as ideas for their own Reels.

## Rules
- Search the public web only (web search). No logging in, no scraping, no platform automation.
- Platforms: TikTok, YouTube (Shorts), Facebook (Reels/videos), X. Aim for at least one per platform when good ones exist.
- Only respectful Quran recitation content: clear recitation, calm nature/space visuals or clean text, no music,
  nothing sectarian, political or sensational. Prefer well-known reciters and high engagement.
- Never suggest a URL already in `suggestions.json` (sent or not). Only direct links to one video
  (not profiles, playlists or search pages). Open each link (web fetch) to confirm it exists when possible.
- `why`: one short sentence on what makes it worth copying (hook, pacing, visuals, caption idea). Never copy
  their caption text.

## Output
Append to `suggestions.json` (a JSON list) objects like:
```json
{"platform": "tiktok", "url": "https://www.tiktok.com/@.../video/...", "title": "Surah Ar-Rahman over waterfall footage",
 "why": "Opens on the strongest ayah in the first second; slow waterfall b-roll.", "found": "2026-11-25"}
```
`platform` is one of `tiktok`, `youtube`, `facebook`, `x`. Keep the file valid JSON. Commit with message
`scout: N video ideas` and push to `main` (pull --rebase first). The Telegram bot sends new entries to the owner
on its next run and marks them `sent`.
