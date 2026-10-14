Използвай captain скила (капитан, /captain 2h) за тази задача в digital-archives.

Задача (ЛН2): двете независими части от жизнения цикъл на разрешенията, които не зависят от
статусите. Обзорът и решенията на owner-а от 13.10.2026 са в
`docs/plans/2026-10-13-permit-lifecycle-overview.md` (раздел „Решения на owner-а“) — решени са, не
ги отваряй наново.

1. **Модулът РБ2a „скан → Gemini“** по `docs/plans/2026-10-13-permit-issue-scan-ai-read-design.md`,
   само ИВ11, ИВ12, ИВ14, ИВ15, ИВ20 и тестовете ИВ31: `permit_authoring/services/scan_read.py`
   (растеризиране, № и дата, дата на влизане в сила по етикета „ВЛИЗА В СИЛА НА“ на всички прочетени
   страници, пълен OCR текст), сглобителят `printed_text`, нормализацията и формулата на процента
   (числата се пазят с всякаква дължина), настройките `permit_scan_read_enabled` (по подразбиране
   изключен) и `permit_scan_match_threshold`. Модулът е чиста услуга без endpoint, без UI и без
   migration. Плюс скрипт за калибровката от ИВ33 (token recall срещу `difflib`, модел
   `gemini-3.8-flash`), който се пуска локално на 5–10 скана; истински сканове не влизат в repo-то.
   Ако сканове за калибровка няма локално — питай owner-а къде са.
2. **Новото право** `permit_in_force_marking` „Маркира разрешения като влезли в сила“ по
   `docs/plans/2026-10-13-permit-in-force-reminders-design.md` (само частта за правото: ключ в
   `permissions_config.py`, етикет в `grant_label` и в `frontend/src/utils/auditLabels.ts`, екранът
   „Потребители“ го показва и дава). Само за `building_permit`, независимо от „Създава разрешения“,
   действа само при достъп до регистъра. Нищо още не го проверява — действията идват с РБ3/РБ4.

Извън обхвата: endpoint-ите `scan-read`/`issue`, таблиците `permit_scan_reads` и
`permit_in_force_watch`, диалогът за извеждане, статусите (РБ1), РБ3, РБ4. Паралелно друга сесия
(ЛН1) прави РБ1 — не пипай `publish.py`, `authored_visibility.py`, `permit_register.py`,
`PermitStatusFilter`, `PermitPublishDialog`, alembic migration-ите.

Branch и worktree: работи върху branch-а на ТОЗИ worktree (създаден от supacode от `main`). Owner-ът
избира него за основа на captain run-а (ОП2 при bootstrap) — не създавай отделен `captain/*` branch.
Сливане в `main` — само с `/captain merge main` от owner-а.

Правилата на проекта са в `CLAUDE.md` (clean-code метрики, локалните проверки `backend/scripts/lint.sh`,
`frontend/scripts/lint.sh`, pytest, tsc, vitest, Codex ревю). UX въпрос, който спекът не решава →
първо 3amigos, после owner-а.
