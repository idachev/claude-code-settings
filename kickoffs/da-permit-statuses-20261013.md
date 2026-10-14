Използвай captain скила (капитан, /captain 2h) за тази задача в digital-archives.

Задача: имплементирай РБ1 — статусите и етикетите на авторските разрешения — по спека
`docs/plans/2026-10-13-permit-statuses-labels-design.md`. Обзорът и решенията на owner-а от
13.10.2026 са в `docs/plans/2026-10-13-permit-lifecycle-overview.md` (раздел „Решения на owner-а“).
Те са решени: не ги отваряй наново.

Обхват (ЛН1):
- статусите `draft` „Чернови“ → `issued` „Изведени от деловодството“ → `in_force` „Влезли в сила“;
- **само стъпка А** на migration-а от СТ16 (разширяване на CHECK-а, кодът пише `issued`, чете и
  `published`, и `issued`); стъпка Б (data migration и стесняване) е отделен деплой — не я прави сега,
  запиши я в TODO;
- предикатите за видимост, `permit_register.py`, табовете (`PermitStatusFilter`; таб „Влезли в сила“
  остава забранен, докато РБ3 не е готов), чипът, корицата, breadcrumb, audit етикетите, бутонът
  „Изведи от деловодството“ вместо „Публикувай“ (диалогът засега без AI четене — то е РБ2).

Извън обхвата: РБ2 (скан → AI четене, OCR сравнение, таблиците `permit_scan_reads` и
`permit_in_force_watch`), РБ3, РБ4. Паралелно друга сесия (ЛН2) прави модула `scan_read.py`,
формулата за сравнение и новото право `permit_in_force_marking` — не пипай
`backend/app/permit_authoring/services/scan_read.py` и `backend/app/governance/services/permissions_config.py`.

Branch и worktree: работи върху branch-а на ТОЗИ worktree (създаден от supacode от `main`). Owner-ът
избира него за основа на captain run-а (ОП2 при bootstrap) — не създавай отделен `captain/*` branch.
Сливане в `main` — само с `/captain merge main` от owner-а.

Правилата на проекта са в `CLAUDE.md` (UI гейтовете преди UI код, clean-code метрики, локалните
проверки `backend/scripts/lint.sh`, `frontend/scripts/lint.sh`, pytest, tsc, vitest, Codex ревю).
UX въпрос, който спекът не решава → първо 3amigos, после owner-а.
