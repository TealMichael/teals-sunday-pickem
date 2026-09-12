# Teal's Sunday Pick'em v1.0.7-hotfix7.1 — Rich Ticker Render Repair

This is a narrow clock-rendering repair for Hotfix 7.

## Root cause
The Hotfix 7 feed used the legacy AWTRIX 3 colored-fragment shape:
`{"t":"CHI","c":"F56600"}`

This clock runs AWTRIX NG, whose rich-text schema is:
`{"text":"CHI","color":"F56600"}`

The Berry `notify()` call accepted the outer notification, but the fragment objects had no recognized
text field, so the physical panel showed a blank/black notification for a few seconds.

## Fix
- Server-generated fragments now use AWTRIX NG `text` / `color` keys.
- New DB migration 010 updates the clock-feed function's synthetic/manual rich fragments.
- The AWTRIX script normalizes BOTH formats (`text/color` and legacy `t/c`) before rendering.
- If a rich notification is rejected, it falls back immediately to readable plain text.
- Whole-line fallback color is now passed as AWTRIX NG `textColor`.
- Unsupported emoji were removed from the physical ticker copy because AWTRIX NG renders unsupported
  emoji as `?`. Caleb keeps the Bears personality through orange/blue accents and wording such as
  `BEAR DOWN? DON'T JINX IT`.

No scoring, lineup, lock, pool, injury, NFL-refresh cadence, or standings logic changes.
