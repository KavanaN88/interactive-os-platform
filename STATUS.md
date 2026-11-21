# OS LAB – Build Status

## Summary
All 10 simulation modules, Compare, Learn (lessons + quizzes), Terminal, a welcome page, accounts (student / administrator)
and the Admin dashboard are implemented. NOT built: Docker for the app itself, module/algorithm management in Admin.

## Accounts and Admin (new in this build)
- Accounts, sessions, audit log, usage events, quiz attempts, lesson progress and admin-created content are stored in SQLite
  (`backend/data/oslab.db`, created automatically). DEVIATION FROM THE ORIGINAL PLAN: the spec said PostgreSQL + SQLAlchemy.
  SQLite with parameterised SQL was chosen so the whole security-critical layer could be tested here. The PostgreSQL models and
  Alembic setup from earlier phases are unused. Moving the store to PostgreSQL later means replacing `app/auth/store.py`.
- Passwords: Argon2id when `argon2-cffi` is installed (it is in requirements.txt), scrypt otherwise. JWT access tokens are HS256
  implemented with the standard library and checked against the published jwt.io known-answer vector; `alg: none` and tampered
  tokens are rejected. Refresh tokens are random, stored only as SHA-256 hashes, rotated on every use, with theft detection
  (late reuse revokes all sessions) and a 10 s grace for two concurrent requests. The refresh token is an httpOnly SameSite=Strict
  cookie, and refresh/logout also require a custom header (CSRF defence). Roles are read from the database on every request, so a
  demotion or deactivation applies immediately.
- Login: one generic error for unknown user and wrong password, equal work for unknown users, 5 failures lock an account for 15 min,
  login rate-limited to 10/min per address, sign-ups to 10/hour.
- Admin API: a router-level guard requires an administrator on all 18 routes (401 guest, 403 student); tests assert this
  structurally and that no other router exposes an /admin path. Admins cannot change/delete themselves or remove the last active
  administrator. Every admin action is written to the audit log.
- Admin features: overview analytics (students, active/inactive accounts, simulation executions, most-used modules, quiz participation
  and average, learning completion), user search/filter/role/activate/reset password/delete, lessons and quiz-question create/edit/
  delete/publish/hide (built-in items can be hidden), student performance and module completion reports, audit log.
- Analytics are real recorded activity: successful simulation requests (any visitor), graded quizzes, lesson completions of
  signed-in students. Nothing is estimated.

## Not covered by Admin
Managing the list of modules and algorithm descriptions (they are fixed in code). Per-user history beyond progress and quiz attempts.

## What was verified in the build sandbox (no network, so no FastAPI / Vite / Postgres here)
- 238 backend tests pass offline (`python run_tests_offline.py`): every engine, the terminal's security rules, the quiz engine,
  the rate limiter, password/JWT/session/admin logic, and API contract tests. Expected values are textbook results or hand calculations
  (e.g. 15/12/9 page faults, Belady 9->10, disk 640/236/236/382/208/322, Banker's safe sequence, thrashing hump at 5 processes).
- The API contract test runs the REAL router handlers and schema classes (with FastAPI/Pydantic stand-ins) using the exact
  JSON each frontend page sends; unknown or missing fields fail. It also checks that every route the frontend calls exists
  with the right method, and was shown to catch a deliberately mistyped route.
- Lessons: every number quoted in the 30 lessons is recomputed from the engines in tests/test_learn.py.
- Quiz numerical answers are computed by the engines at grading time; correct answers are never sent before submission.
- All 15 pages, the navigation and the whole app were rendered to HTML (26 checks) with no exception and no React warning, in
  guest, student and administrator states.
- Frontend/backend data shapes: the TypeScript interfaces of the Admin, Learn, Analyzer and Virtual Memory pages are parsed and
  compared with real backend output (a renamed field was shown to be caught). 62 API calls from the frontend are matched to real routes.
- Frontend: 39 files, 0 syntax errors, all relative imports resolve, the only type errors are caused by the missing
  react/vite type packages. 26 render checks draw every visual component with real engine output and compare what is
  drawn to the backend data; the input parsers pass 15 checks.
- Testing found and fixed (among others): a thrashing model that behaved unrealistically, a vacuous assertion habit
  (all `or True` tests removed), a focus-loss bug in the matrix editor, an invalid SVG title, and a performance problem
  (see below).

## Performance (measured, worst allowed inputs)
- CPU Round Robin, 100 processes, quantum 1: 99 ms and 5 MB (was 660 ms and 83 MB before traces were bounded at the source).
- Analyzer comparing all 8 CPU algorithms on 100 processes: 0.8 s. Every other engine ran in under 75 ms at its limit.
- Traces are capped at 5000 recorded steps; metrics and Gantt always come from the full run (tested).

## NOT verified (cannot be run here)
`npm install`, `npm run build/dev`; a real browser session (clicking, typing, cookies, animation); the live FastAPI server including
the lifespan start-up, middleware and real cookie handling; the Argon2id code path (scrypt is what ran here); Admin tables rendering
live data (the data shapes are verified, the first render only shows 'Loading'). tests/test_api_cpu.py, test_api_modules.py and
test_api_auth_admin.py need `pip install -r requirements.txt` then `pytest`. Expect small first-run fixes; send me the exact error text.

## Known limits and honest gaps
- Saved comparisons and (for guests) lesson progress and quiz history stay in the browser (localStorage); signed-in students' progress and quiz attempts are also stored on the server.
- Quiz bank is small: 30 multiple-choice questions plus engine-generated numerical questions (6 per module for "all levels").
  The quiz timer runs in the browser and is not enforced by the server.
- Memory: paging and segmentation are not simulated (see Virtual Memory for paging). Deadlock prevention is explained,
  not simulated. Readers-writers implements reader preference only.
- Terminal sessions live in server memory (lost on restart); history is not saved to the database.
- No Docker image for the app itself, only Postgres + pgAdmin.
- Colours follow the spec palette (electric blue), not the purple of your first mockup.

## Next steps (suggested)
1. Run it and send any errors.
2. Optional: move the account store to PostgreSQL, add module/algorithm management to Admin, a Docker image for the app.
