# Overload batch 2 (Dec 5–14, 2026)

Ten feature videos for @overloadlifts (TikTok) and the Overload Facebook Page, posted daily at 6:30 PM ET.

- `batch2.json`: per-video hook, screens, captions (TikTok + Facebook), date, music. `approved` flips to true once Mike approves.
- `screens/`: app screens captured from the real app (Pro test build, sample history) by `capture.py`.
- `render.py`: builds `videos/NN-id.mp4` (stock hook from Mixkit's dark-warehouse series, app screens, batch-1 end card, batch-1 Mixkit music).
- `endcard.mp4`: the batch-1 end card, reused for consistency.
