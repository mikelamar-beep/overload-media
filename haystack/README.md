# Haystack social videos (TikTok + Facebook Reels)

Same workflow as Overload: stock footage + captions + end card + music, rendered here, hosted here, and queued in Buffer.

## Files
- `render.py` – renders a batch file into 1080x1920 MP4s (`python3 render.py batches/batch-02.json --out /tmp/hs-out`). Needs ffmpeg + Pillow. Downloads Mixkit clips/music on demand.
- `library.json` – vetted Mixkit clip IDs by mood, and music track IDs.
- `batches/batch-NN.json` – the scripts (scenes, captions, first comment). `"approved": true` means Mike OK'd the batch for posting.
- `videos/batch-NN/<id>.mp4` – finished videos. Buffer pulls them from
  `https://cdn.jsdelivr.net/gh/mikelamar-beep/overload-media@main/haystack/videos/batch-NN/<id>.mp4`
- `state.json` – what has been queued (video id → date, Buffer post ids).

## Posting schedule (America/New_York)
One video a day to both Haystack channels: Sun–Thu 7:30 PM, Friday 12:30 PM (before sundown), Saturday 9:00 PM (after sundown).

## Content rules
- Audience: Seventh-day Adventist singles, marriage-minded. Warm, faith-friendly, light humor.
- Never show or imply real members, member counts, matches or testimonials that aren't real. No seeded test profiles.
- Only describe features that exist (check the app repo's CLAUDE.md). Sabbath Mode (app pause) was removed Nov 2026: don't mention the app resting on Sabbath.
- Footage: no alcohol, kissing, meat dishes, jewelry close-ups, or other-faith imagery. Use clips from `library.json`; add new Mixkit clips only after checking a frame of each.
- On-screen text has no emoji (the font can't draw them); emoji are fine in captions.
- TikTok caption ends with: Search "Haystack Adventist Dating" on the App Store + 5 hashtags.
- Facebook caption ends with "link in the comments 👇"; the first comment carries the App Store link.
- New batches are 10 videos and need Mike's approval before posting (`approved` stays false until he says go).
