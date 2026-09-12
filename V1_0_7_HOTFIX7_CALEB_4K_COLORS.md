# Teal's Sunday Pick'em v1.0.7-hotfix7 — Caleb 4K Watch + Rich Sunday Ticker

## Purpose
Add one playful Sunday-clock feature and improve the whole clock's visual readability without touching Pick'em scoring, lineups, lock rules, pool logic, injury rules, or the NFL refresh cadence.

## Design rule
White remains the default reading color. Color is used only to communicate identity or meaning.

- NFL team abbreviations use readable team-color accents.
- Player names use their NFL team's readable accent color.
- Pick'em labels use a small amount of teal / purple / light-blue / gold.
- Scores, clocks, stat ingredients, and most explanatory copy remain white.
- First place / champion emphasis uses gold.
- Readiness success uses green; warnings use orange.
- Caleb's special watch uses Bears orange + a readable Bears-blue accent + white stats.

Dark official team primaries are brightened where necessary for a black 8x32 LED matrix.

## Caleb 4K Watch
The watch tracks Caleb Williams toward 4,000 season passing yards.

Example while the Bears are live:
`🐻 CALEB 4K WATCH 🐻 • TODAY: 287 YDS • SEASON: 2,941 YDS • 1,059 TO 4K • PACE: 4,165 👀 • BEARS FANS, DON'T JINX IT`

Color treatment:
- `🐻 CALEB 4K WATCH 🐻` — Bears orange
- TODAY / SEASON stats — white
- yards remaining to 4K — readable Bears blue
- pace above 4K — green
- troll line — Bears orange

If pace falls below 4K:
`PACE: 3,812 • BEARS HISTORY STILL WAITING...`

If 4,000 is reached:
`CALEB WILLIAMS: 4,000+ • CHICAGO FINALLY HAS A 4K PASSER 😱`

### Data behavior
- Prior-week season baseline comes from nflverse once per Pick'em week and is cached.
- A prior Thursday/Monday Bears game still counts even though it is not a Pick'em game.
- During a Sunday Bears game, current-game passing yards come from ESPN's live box score.
- Provider trouble preserves the last good Caleb watch and never impacts Pick'em scoring.
- Pace is a 17-game projection.

## Sunday cadence
Core Hotfix 5 cadence remains unchanged:
- Weekly Pick'em standings: :00, :15, :30, :45
- NFL LIVE scores: :05, :20, :35, :50

Bears not live:
- :10 Pick'em player update
- :25 Pick'em Pulse (Week 1) / Season standings (Week 2+)
- :40 Caleb 4K Watch
- :55 Commissioner message

Bears live:
- :10 Caleb 4K Watch
- :25 Pick'em player update
- :40 Caleb 4K Watch
- :55 Commissioner message

## Message examples
NFL LIVE:
- `NFL LIVE • CHI 21 • MIN 17 • Q3 4:22`
- CHI is Bears orange; MIN is Vikings purple; scores/time stay white.

Weekly standings:
- `PICK'EM LIVE` in teal
- first-place name in gold
- scores accented teal
- remaining names/separators white

Player update:
- `PLAYER UPDATE` gold accent
- player name in team color
- fantasy points gold
- stat ingredients white

Pick'em Pulse:
- label / owner emphasis purple
- NFL player name in team color
- explanatory copy white

Commissioner:
- `WELCOME`, `SUNDAY AT TEAL'S`, or `FROM THE COMMISH` orange
- message copy white

## AWTRIX transport
Hotfix 7 now uses AWTRIX colored-text fragments (`text` as an array of `{t, c}` fragments) instead of painting the entire ticker one color. Plain-text + single-color fallback remains available if fragments are absent.

## Test Clock
Test Clock cycles mixed-color examples, including:
- connection/readiness accent
- Commissioner message
- Pick'em standings
- an NFL score with CHI/MIN team colors
- Bears-themed Caleb 4K Watch

## Protected areas unchanged
- Pick'em fantasy scoring
- Kicker scoring
- 1:00 PM database lock
- Saved lineup / pool immutability
- Injury / emergency backup behavior
- GitHub NFL refresh cadence
- Hotfix 6 Sunday reliability protections
- Scoped AWTRIX token / public wrapper RPC architecture
