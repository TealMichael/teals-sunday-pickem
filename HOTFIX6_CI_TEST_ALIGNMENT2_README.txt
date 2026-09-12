Teal's Sunday Pick'em v1.0.7-hotfix6 — CI Test Alignment 2

This is a TEST-ONLY correction.

GitHub still had the pre-AWTRIX-hotfix assertion expecting:
  /rest/v1/rpc/clock_feed
  /rest/v1/rpc/clock_ack

The current working production architecture intentionally uses the public wrapper RPCs:
  /rest/v1/rpc/pickem_clock_feed
  /rest/v1/rpc/pickem_clock_ack

Those wrappers were introduced after the private-schema RPC path returned HTTP 404.
The physical clock is already working through the wrapper path.

This patch updates only:
  tests/test_v107_sunday_clock.py

NO production Python changes.
NO AWTRIX script changes.
NO Supabase SQL.
NO hidden files.

Validation against the current simulated repository after replacing this stale test:
  217 passed
