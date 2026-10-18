# Blast Radius и CC Safety Net при нощни и away run-ове — предложение за промяна

Дата: 2026-10-15. Статус: **ревизирано 2026-10-17** (виж §8): Blast Radius е махнат, fork-ът на Safety Net е
инсталиран на 2026-10-18. Остават ОС3 (махане на РШ9) и ОС4 (анализ след следващ away run).
Източник на числата: анализ ЗД19 на captain run `20261015-031332` в repo `plexibits-dev/ivan-games`
(`tmp/captain/20261015-031332/reports/denials-ЗД19.md`, скрипт `denials-ЗД19.py` до него). Период 03:00–07:40, 77 transcript-а.

## 1. Проблемът

Двата guardrail-а пазят от различни неща:
- **CC Safety Net** (`cc-safety-net@cc-marketplace`, 2.6.11) е hook, който отказва Bash команди по правила. Тук важи правилото
  `secret.home.gcloud-config`, което пази `~/.config/gcloud/`.
- **Blast Radius** (`blast-radius@ai-marketplace`, примерен mod на Anthropic) задържа „рискови“ Bash команди (`rm -r/-f`,
  `git reset --hard`, `git clean`, force push, миграции). Показва pane с Proceed/Cancel и чака човек. След 10 мин
  (`HOLD_LIMIT_MS`) отказва. Държи само **една** команда наведнъж за всички агенти.

В нощен или away run няма човек на компютъра. Тогава Blast Radius само бави, а Safety Net съвпада с текст, а не с истински достъп.

| ID | Guardrail | Откази | Полезни (TP) | Фалшиви (FP) | Цена |
|---|---|---|---|---|---|
| ПБ1 | CC Safety Net (`secret.home.gcloud-config`) | 2 | 1 | 1 | ~5 мин и 2 решения на Иван |
| ПБ2 | Blast Radius | 4 (+2 пуснати след Proceed) | 0 | 4 | **43,8 мин** чакане на агенти |

Подробно:
- **ПБ3.** Всички 4 отказа на Blast Radius са „no answer within 10 minutes“. Агентите трият **собствени** временни файлове:
  стари снимки в `tmp/captain/…/shots/`, своя scratchpad, пробни mp3 в своя worktree. Всичко това се прави наново или git го връща.
  Най-скъпият случай: 826 s (226 s на опашка зад друг агент + 600 s задържане).
- **ПБ4.** Safety Net SN1 (07:01) е **полезен**: командата наистина ползва service account ключа.
- **ПБ5.** Safety Net SN2 (07:25) е **фалшив**: пътят `~/.config/gcloud/sa-keys/` е само дума в текста на Codex prompt-а,
  който runner-ът пише с `cat > file <<EOF`. Никой ключ не се чете.
- **ПБ6.** Иван commit-на `.cc-safety-net/policy.json` с `allow_paths: ["~/.config/gcloud/sa-keys/"]` (commit `20cf57f3c`). Това не помогна:
  `getProjectPolicyPath(cwd)` (`cc-safety-net/2.6.11/dist/bin/core.js:545`) чете project policy само от `<cwd>/.cc-safety-net/policy.json`
  и не търси нагоре до git root. Агентът е бил в `site/web`. Worktree-ите под `.claude/worktrees/<име>` също имат свой cwd.

## 2. Целта

- **ЦЛ1.** В нощен или away run агентите не чакат човек, който го няма.
- **ЦЛ2.** Истинското четене или ползване на таен ключ остава спряно (SN1 трябва пак да се спре).
- **ЦЛ3.** Дума за пътя в текст (prompt, документ, commit message) не спира работата.
- **ЦЛ4.** Едно разрешение (allow path) важи навсякъде: корен на repo-то, подпапка, worktree.

## 3. Предложенията

### Blast Radius

- **ПР1 (препоръчвам).** Blast Radius да е изключен, когато никой не гледа. Варианти:
  - ОП1а: captain в away режим не го включва за run-а. Например env флаг, който hook-ът проверява, или изключване на plugin-а за сесията.
  - ОП1б: hook-ът сам проверява дали има човек (същата проверка за idle като `notify-when-away.sh`, macOS `HIDIdleTime`).
    Ако няма вход повече от N минути, пропуска задържането и пише ред в лог.
  - Защо е безопасно: истински опасните команди (`rm -rf /`, `rm` извън repo-то, force push към master) се пазят и от Safety Net
    (`destructive_command_protection`) и от правилата на captain (R10). Blast Radius сам казва, че е „preview layer, not a permission system“.
- **ПР2.** Ако Blast Radius остане включен, да има allow list без задържане за:
  - `rm` в `<repo>/tmp/**`, в scratchpad на сесията (`/private/tmp/claude-*/**`) и в собствения worktree `<repo>/.claude/worktrees/<име>/**`,
    когато файловете там не са tracked в git или са възстановими;
  - по-кратък `HOLD_LIMIT_MS` в нощен режим (например 60 s вместо 10 мин).
  Нужен е fork на мода (`HOLD_LIMIT_MS`, `classifySegment`), защото днес няма настройка за това.
- **ПР3.** Опашката да е по агент, не обща. Сега една задържана команда кара всички останали агенти да чакат.
- **ПР4.** Пресмятането да разгъва променливи (`$S`). Днес `rm -rf $S` показва „delete nothing“ и пак задържа (БР2).

### CC Safety Net

- **ПР5 (препоръчвам).** Allow path-ът за `~/.config/gcloud/sa-keys/` да е в **user** policy-то на Safety Net
  (`npx cc-safety-net gui` или `~/.cc-safety-net/`), не в repo-то. Тогава важи при всеки cwd и във всеки worktree (ЦЛ4).
  Commit-натият `.cc-safety-net/policy.json` в `ivan-games` може да остане за колегите, но сам не стига.
- **ПР6.** Предложение към plugin-а: project policy да се търси нагоре от cwd до git root, както `.gitignore`. Тогава ПБ6 изчезва.
- **ПР7.** Captain и агентите да пишат текстови файлове (Codex prompt-и, доклади) с **Write tool**, а не с `cat > file <<EOF` в Bash.
  Правилото `secret.home.*` гледа текста на Bash командата. Не е проверено дали Safety Net гледа и съдържанието при Write.
  Това трябва да се провери преди промяната в captain skill-а.
- **ПР8.** Предложение към plugin-а: правилата `secret.home.*` да съвпадат само когато пътят е **аргумент** на команда, която чете,
  копира или подава файла (`cat`, `cp`, `<`, `--cred-file`, `*_CREDENTIALS=`). Пътят в heredoc тяло или в `echo "…"` да не съвпада.
- **ПР9.** `secret.home.gcloud-config` да остане включено за истински достъп (ЦЛ2). Проверки, които наистина четат ключ,
  captain да дава направо на Иван като `!` команда, а не на runner. Така не се губи ход за отказ, който е сигурен.

## 4. Как ще знаем, че работи

- **ПТ1.** Следващ away run с няколко writer-а: 0 отказа „no answer within 10 minutes“ и 0 секунди на опашка в Blast Radius.
- **ПТ2.** Runner от `site/web` и от worktree пише prompt с думата `~/.config/gcloud/sa-keys/` и не е спрян.
- **ПТ3.** `GOOGLE_APPLICATION_CREDENTIALS=~/.config/gcloud/<друг>.json gcloud …` (ключ извън allow path) пак е спрян.
- **ПТ4.** Анализът на отказите (скриптът `denials-ЗД19.py`) се пуска пак след run-а и показва ПТ1–ПТ3.

## 5. Извън обхвата

- Captain guard-ът (`hooks/guard.py`, 5 отказа) и класификаторът на auto mode (3 отказа). Те са отделна тема.
- Промени в IAM или в самите ключове.

## 6. Решения (Иван, 2026-10-15)

Всички въпроси от §7 са затворени в една сесия, един по един.

### Blast Radius
- **РШ1 (ОТ1).** ОП1а: в away run captain изключва задържането.
- **РШ2 (ОТ1а).** Mod-ът няма настройка за изключване и не чете env (работи през API `$`). Затова го копираме от
  `anthropics/claude-code-playground` на commit `569c528` в `ai-marketplace/plugins/blast-radius` (Apache-2.0).
  Записът в `marketplace.json` сменя `git-subdir` с `./plugins/blast-radius`. Mod-ът проверява файл-флаг
  (например `~/.claude/captain/away.flag`). Ако флагът съществува, пуска командата без задържане и пише ред в лог.
  Captain създава флага в началото на away run и го трие в края.
- **РШ3 (ОТ1б).** В копието правим още ПР2 (allow list), ПР3 (опашка за всеки агент) и ПР4 (разгъване на променливи).
- **РШ4 (ОТ1в).** `rm` в собствения worktree минава без задържане само ако нищо не се губи: всички файлове са
  игнорирани от git или са в git без промени. Файл с промени без commit или нов файл извън `.gitignore` се задържа.

### CC Safety Net
- **РШ5 (ОТ2).** Правим своя версия. Клонът е в `~/develop/github/kenryu42/cc-safety-net`.
- **РШ6 (ОТ2а).** Нашият branch тръгва от `main` на автора (на 2026-10-17 това е `v2.6.13`).
- **РШ7 (ОТ2б).** Правим ПР6 (project policy се търси нагоре до git root) и ПР8 (`secret.home.*` спира само когато
  пътят е аргумент на команда, която чете файла). ПТ3 трябва да остане зелен.
- **РШ8 (ОТ2в, ОТ2г).** Fork `mentorano/cc-safety-net` в GitHub. `ai-marketplace` сочи към fork-а с `git-subdir`
  на фиксиран sha. `cc-safety-net@cc-marketplace` се изключва.
- **РШ9 (ОТ2д).** ПР5 временно: allow path в user policy, докато нашата версия с ПР6 не е инсталирана. После се маха.
- **РШ10 (ОТ4).** Fork-ът не се обновява сам. И досега `cc-marketplace` нямаше `autoUpdate`. Решение: ред в README
  на `ai-marketplace`, че fork-ът се обновява ръчно от автора. Без автоматична проверка.

### Captain
- **РШ11 (ОТ3).** Captain не се променя за Write tool. Стига ПР8. Проверено в кода (`dist/bin/core.js:2192`,
  `dist/bin/gate.js:769`): при `Write`/`Edit` Safety Net гледа само ключовете за път, не `content`.
- **РШ12 (ПР9).** Captain дава проверки, които четат таен ключ, направо на Иван като `!` команда. В away run те
  влизат в опашката за края на run-а, както деструктивните действия.
- **РШ13 (от РШ2).** Captain създава и трие away флага за Blast Radius.

## 7. Отворено (затворено, виж §6)

- **ОТ1.** За Blast Radius: ОП1а (изключен в away), ОП1б (сам усеща idle) или ПР2 (allow list + кратък лимит)?
- **ОТ2.** ПР5 сега (user policy, един ред в GUI-то) и ПР6/ПР8 като предложения към авторите на plugin-а. Съгласен ли си?
- **ОТ3.** ПР7: да се промени ли captain skill-ът да пише prompt файловете с Write tool, след проверката от ПР7?

## 8. Ревизия 2026-10-17: махаме Blast Radius, оправяме fork-а на Safety Net

### Данни (транскрипти от 15.10 до 17.10, 505 файла)
- **ДН1.** Blast Radius: 22 отказа, всички „no answer within 10 minutes“, 0 Cancel, 0 полезни. 15 × 600 s ≈ 2,5 часа
  чакане на агенти. Всички цели са собствени файлове на агента или миграции на тестова база.
- **ДН2.** Около 10 от 22-та отказа са извън away run. Затова флагът от РШ1/РШ13 не стига.
- **ДН3.** Blast Radius задържа и текст: думата за миграция в низ или в heredoc. В сесията от 17.10 това стана три
  пъти с команди, които само пишат файлове.
- **ДН4.** Safety Net: 35 отказа, всеки струва по един ход. Два фалшиви отказа спряха subagent.
- **ДН5.** Главната причина за фалшивите откази по `secret.home.*`: heredoc през `command cat` (правилото от
  CLAUDE.md) се сканира като shell. С bare `cat` същият текст минава.

### Решения (Иван, 2026-10-17)
- **ВП1 → ОП1.** Blast Radius се маха изцяло. РШ1–РШ4, РШ13, ПР2–ПР4 и ПТ1 отпадат.
- **ВП2 → ОП3.** Приемаме, че `rm -r` на работа без commit вече не се задържа.
- **ВП3 → ОП5.** Rulebook `db-guard` в user rules: `alembic downgrade`, `docker volume rm|prune`,
  `docker compose down -v`. `dropdb`, `psql -c "drop database …"` и SQL в heredoc не могат да се хванат с rulebook.
- **ВП4 → ОП7.** ПР8 важи за всички `secret.*` и за `guard.policy-config`.
- **ВП5 → ОП9.** `git checkout -- <file>` остава спрян.
- **СН1 → ОП11.** `docker exec … psql <<'EOF'` с `k.key` остава спрян. Тялото се чете като shell нарочно
  (`docker exec`/`ssh` пускат shell).
- **СН2 → ОП13.** Python heredoc със `s.replace('<път>', …)` остава спрян (`Path.replace` пише).
- **ИЗ1 → ОП15.** Fork `mentorano/cc-safety-net` в GitHub (публичен, както всеки fork на публичен repo).
- **ИЗ2 → ОП17.** Commit без push в `ai-marketplace` и `~/.claude`.

### Направено
- **НП1.** `blast-radius@ai-marketplace` е деинсталиран. Записът и README разделът в `ai-marketplace` са махнати.
- **НП2.** Fork branch `ivan/secret-text-false-positives` (3 commit-а върху `v2.6.13`, `bun run check` зелен):
  - `command cat`/`env cat` heredoc е запис на данни, както bare `cat` (реален случай 5 вече минава);
  - `git diff|log|show|status|blame` може да назовава policy файла (реален случай 1 вече минава);
    присвояване, `env`, `-c`, `--config-env` и `--output` пазят стария отказ;
  - ПР6: project policy се чете от най-близката `.cc-safety-net/` до git root (и в worktree).
    Относителните `allow_paths` се разрешават спрямо този корен. Root policy-то е защитено и от поддиректория.
- **НП3.** `ai-marketplace`: запис `cc-safety-net` към fork-а на sha `3b4fe37a`, ред в README за ръчното
  обновяване (РШ10). Тестът за външни plugin-и приема и `url` източник със sha.

### Остава
- **ОС1.** Направено 2026-10-18: push на `ai-marketplace` (`main` на `cfed839`) и на `~/.claude`.
- **ОС2.** Направено 2026-10-18: `cc-safety-net@ai-marketplace` е инсталиран на `3b4fe37a` и е проверен (smoke
  тест, `db-guard`, реалните откази). `cc-safety-net@cc-marketplace` е деинсталиран, а marketplace-ът
  `cc-marketplace` е махнат и от `osx`, и от `master`. Сесиите трябва да се рестартират.
- **ОС3.** РШ9 и ОП5: Иван копира файловете в `~/.cc-safety-net/` на 2026-10-17, проверени са. РШ9 е по избор и временен: allow path в user policy пуска четенето на
  ключовете в `sa-keys/` от агенти във всяко repo, не само в `ivan-games`. Махни го след ОС2.
- **ОС4.** Повторен анализ на отказите след следващ away run (ПТ2–ПТ4).
