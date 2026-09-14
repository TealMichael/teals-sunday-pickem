TEAL'S SUNDAY PICK'EM — HOTFIX 7.9 TUESDAY NEWSLETTER

INSTALL
1. Extract this ZIP.
2. Open the visible folder named UPLOAD_TO_GITHUB.
3. In GitHub, open the repository ROOT (main/top level).
4. Upload the CONTENTS of UPLOAD_TO_GITHUB, preserving the tests folder.
   - Root replacements/new files:
     config.py
     app.py
     store.py
     gate5_ui.py
     newsletter.py
     V1_0_7_HOTFIX7_9_TUESDAY_NEWSLETTER.md
   - tests/:
     test_v107_hotfix79_tuesday_newsletter.py
5. Commit the upload.
6. Wait for the Pickem Quality Gate to turn green.

NO SUPABASE SQL IS REQUIRED.
NO AWTRIX REINSTALL IS REQUIRED.
NO GITHUB WORKFLOW FILE CHANGES ARE REQUIRED.

GITHUB COMMIT MESSAGE
v1.0.7 hotfix — add Tuesday text newsletter

EXACT TAG
v1.0.7-hotfix7.9

AFTER DEPLOY
Commissioner → Newsletter
- Confirm the app/lineup link. Save it once if needed.
- The newsletter automatically uses the most recently finalized week.
- Edit anything you want.
- Tap Copy Tuesday newsletter and paste into your group text.

VALIDATION
262 tests passed
release_guard.py PASS
