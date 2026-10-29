# Teal's Sunday Pick'em v1.0.11 — Performance Round 2

**Version/tag:** `v1.0.11`  
**Internal build:** `1.0.11-performance2`  
**Base:** exact attached v1.0.10 full-source archive (`1.0.10-performance1`)  
**Commit message:** `perf: release v1.0.11 with coordinated fresh public cache reads`

## Focused changelog

1. Coordinate cold public-bundle misses per week and cache generation. The first reader performs the same original five queries; concurrent readers wait for its completed result. No lock is held while Supabase queries run, and unrelated keys build independently.
2. Make local cache invalidation generation-safe. A read begun before a confirmed local mutation cannot refill the bundle cache after invalidation. This also applies when the cache was initially empty and to explicit fresh reads. A failed builder wakes waiters and leaves no partial cached result.
3. Give authoritative clock and Monday history-archive reads an explicit `fresh=True` bypass of already-cached bundles. A small TTL argument alone had never guaranteed a new read.
4. Invalidate `real_week` after confirmed week-row state updates, without evicting that alias on unrelated pick saves. Guard against an older in-flight alias lookup repopulating it. Return independent nested bundle copies so one viewer cannot mutate another viewer's cache value.

No selection, scoring, commissioner, authentication, newsletter, reaction, schedule, provider, AWTRIX device script, SQL, secrets or dependencies were changed. Default public bundle TTL remains eight seconds. No workers or infrastructure were added.

## Verified measurements

| Same synthetic scenario | v1.0.10 | v1.0.11 |
| --- | ---: | ---: |
| Forced eight simultaneous cold readers of one bundle | 40 logical DB operations | **5** |
| A single cold populated bundle | 5 | **5** |
| Immediate warm bundle | 0 | **0** |
| An eight-second cached bundle requested with `ttl_seconds=0.01` | 0 (cached result) | **0 (same legacy semantics)** |
| Explicit fresh bundle with an eight-second cached entry | Not supported | **5 (authoritative read)** |

The concurrent count is per *one shared server-side store instance*. It is not a measured iPhone page-load time. Fresh clock/archive requests may perform additional reads when a longer cached entry exists; this is an intentional freshness correction. Multiple independent Streamlit worker processes do not share Python memory and cannot be coordinated through this in-process cache. No live provider timing or production scenario was measured.

See `V1_0_11_TEST_REPORT.md` and `V1_0_11_PERFORMANCE_RESULTS.json` for detailed validation and limitations.

## Browser-based installation (football repository only)

**First verify** the football GitHub repository's current `config.py` says `APP_VERSION = "1.0.10"` and `APP_BUILD_VERSION = "1.0.10-performance1"`, or reconcile any newer changes before upload. The v1.0.10 installation was unconfirmed at handoff; a ZIP is not deployment evidence. Do **not** upload to Daily Fact Challenge.

1. Download and unzip `Teals_Sunday_Pickem_v1.0.11_GITHUB_BROWSER_UPLOAD.zip` on your Mac.
2. In a browser, open your existing **Teal's Sunday Pick'em football** GitHub repository at its root (`app.py`, `store.py` and `config.py` should be visible).
3. Choose **Add file → Upload files**. Open the extracted `UPLOAD_TO_GITHUB` folder and drag **its contents**, not the outer folder, into GitHub. Preserve the `tests/...` paths.
4. Confirm the upload shows the intended replacements and new regression/release files, with no `UPLOAD_TO_GITHUB/` prefix in the destination paths.
5. Commit with the exact message: `perf: release v1.0.11 with coordinated fresh public cache reads`.
6. Wait for **Pickem Quality Gate** to pass on the branch your Streamlit app uses. Follow your usual PR/merge process if the branch is protected. After normal deployment, reload the app and check **Build 1.0.11** in Profile.

Do not run reset, regeneration, finalization, correction or AWTRIX test broadcasts merely to check this update. Verify remembered login, five picks/backups, Sunday/Season/History/Profile, the linked Commissioner tools, and unchanged score-age display during normal use.

**Rollback:** Revert the one v1.0.11 browser-upload commit in the football repository, returning the application files to v1.0.10. No database migration, data restoration, clock-script install or secret change is needed. If v1.0.10 was not previously installed, use the last known good football commit instead.

## Packaging

- The **full current app ZIP** contains the complete source tree and all historical SQL, workflow, AWTRIX and test files.
- The **GitHub Browser Upload ZIP** contains only files added/changed from the exact attached v1.0.10 source.
- Both archives are compared by overlaying the small bundle onto the v1.0.10 source and checking byte-for-byte equivalence with the full v1.0.11 project.

Neither archive was deployed or committed remotely by this handoff.
