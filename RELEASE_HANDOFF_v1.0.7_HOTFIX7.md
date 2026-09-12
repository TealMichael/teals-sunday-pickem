# Release Handoff — v1.0.7-hotfix7

Baseline: audited v1.0.7-hotfix6 repository state, Quality Gate green.

Scope: Sunday AWTRIX broadcast presentation plus isolated Caleb 4K watch data.

The final Hotfix 7 design uses mixed-color AWTRIX text fragments rather than coloring whole ticker messages. Most text remains white; NFL team abbreviations and player names use readable team accents, while Pick'em labels and status meanings use limited accent colors.

Caleb 4K Watch:
- Bears orange title/troll copy
- white stats
- readable Bears-blue yards-to-4K
- green pace when projected above 4,000
- orange warning pace when below

Core cadence is unchanged from Hotfix 5. Hotfix 6 reliability protections remain untouched.

Deployment after CI is green:
1. Upload GitHub patch.
2. Run `db/009_clock_colors_caleb_4k.sql` once in Supabase.
3. Replace/reload `awtrix/PickemSunday.ax` on the physical clock.
4. Commissioner -> Clock -> Test Clock and watch the mixed-color samples.

Rollback:
- GitHub: restore Hotfix 6 source.
- Supabase: rerun db/008_clock_nfl_score_cadence.sql.
- AWTRIX: restore Hotfix 6 PickemSunday.ax.

Migration 009 adds no tables/columns; it only replaces `pickem.clock_feed`.
