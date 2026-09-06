# Teal's Sunday Pick'em v0.2.0 — Gate 2 Weekly Game

Gate 2 builds the complete pre-scoring Sunday lineup loop on top of the proven Gate 1 authentication foundation.

## Added
- First-time 3-card onboarding.
- Real Week 1 shell: opens Tuesday Sept. 8, 2026 at noon ET; locks Sunday Sept. 13 at exactly 1:00 PM ET.
- Isolated Gate 2 Test Week so the flow can be tested before Tuesday without affecting Week 1.
- 10 ranked backend pool slots per position with only 5 exposed to players.
- Stable per-session shuffle so ranking order never leaks through card order.
- QB → RB → WR → TE → K one-tap lineup builder.
- Autosave on every starter/backup selection.
- Review My Five + Change buttons + SAVE MY LINEUP confirmation.
- Questionable-player emergency backup flow.
- Database-level universal lock guard on lineup-pick writes.
- Pre-open and pre-lock live countdowns.
- Locked lineup view; incomplete positions remain empty for future 0-point handling.

## Intentionally NOT in Gate 2
- Real NFL player generation/rankings.
- Live injury feed.
- Live scoring.
- Weekly/season leaderboard.
- Full Commissioner tools.
- Winner celebration.

Those remain later gates so Gate 2 can be acceptance-tested independently.
