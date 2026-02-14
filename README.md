# A3 MVP: Реальная логика работы и деплоя

Этот файл фиксирует, как проект **реально** работает в локалке и в проде (Amvera), где находится источник истины, и как выкатывать изменения без сюрпризов.

## 1) Ключевая архитектура (важно)

### 1.1 Локальная разработка
- Код контроллера: `a3_assistant/pipe/a3_controller.py`
- Локальная публикация в pipeline-файл OpenWebUI: `publish.ps1`
- Локальный runtime-файл pipeline: `openwebui_data/pipelines/a3_controller.py`

### 1.2 Прод (Amvera)
- Приложение работает как Docker-сервис (`amvera.yml` + `Dockerfile`).
- В проде у OpenWebUI используется persist-монт:
  - `run.persistenceMount: /app/backend/data`
- БД OpenWebUI: `/app/backend/data/webui.db` (persisted между пересборками).

## 2) Где источник истины для A3-контроллера

Есть 2 источника кода, и это критично:

1. **Pipeline-файл**  
   `openwebui_data/pipelines/a3_controller.py`

2. **DB Function в OpenWebUI (`webui.db`, таблица `function`)**  
   Если в UI выбран `A3 Project Controller` как Function, то фактический код берется из БД.

### Вывод
- Пересборка контейнера **сама по себе не гарантирует** обновление Function-кода в `webui.db`.
- Если меняется логика Function, нужно либо:
  - синхронизировать запись `function` в БД,
  - либо работать только через pipeline-режим, а не через Function.

### Критичное правило для Codex/агента (обязательно)
- По умолчанию считать, что исполняется код из `webui.db` (таблица `function`), если в UI выбран профиль/Function.
- Правка `a3_assistant/pipe/a3_controller.py` и `openwebui_data/pipelines/a3_controller.py` — это только подготовка; без синхронизации в `webui.db` изменения могут не примениться.
- После любой правки логики сначала проверять активный источник исполнения (Function vs pipeline), и только затем считать задачу завершенной.
- Перед ответом "готово" проверять факт применения именно в активном источнике (а не только наличие изменений в файлах репозитория).

### 2.1 Автосинхронизация при старте контейнера (включено)
- При каждом старте контейнера выполняется `a3_assistant/scripts/sync_functions.py`.
- Скрипт синхронизирует в `/app/backend/data/webui.db`:
  - `a3_pm_methodologist` из `a3_assistant/pipe/a3_controller.py`
  - `smart_infographic` из `a3_assistant/actions/smart_infographic.py`
  - `export_to_word_enhanced_formatting` из `a3_assistant/actions/export_to_word_enhanced_formatting.py`
- После синхронизации запускается OpenWebUI (`a3_assistant/scripts/start_with_sync.sh`).
- Это устраняет ручные правки `webui.db` после каждого деплоя.

## 3) Стандартный процесс изменений (dev -> prod)

### Шаг 1. Локальная проверка
1. Изменить `a3_assistant/pipe/a3_controller.py`
2. Локально опубликовать:
   - `.\publish.ps1`
3. Проверить в локальном OpenWebUI:
   - ключевые команды (`/summary`, и т.д.)
   - критичный сценарий, который менялся

### Шаг 2. Git
1. `git add ...`
2. `git commit -m "..."`
3. `git push origin main`
4. `git push amvera main:master`

### Шаг 3. Amvera
1. Нажать `Пересобрать проект` (не просто перезапустить).
2. Проверить runtime-логи.
3. Проверить сценарий в прод-UI.

## 4) Проверка, что прод реально обновился

Минимальный чек:
1. В логах сборки должен быть актуальный коммит (`HEAD is now at ...`).
2. После старта контейнера в runtime-логах не должно быть ошибок парсинга Function.
3. В UI поведение должно соответствовать изменению (не только сборка успешна).

## 5) Типовые проблемы и причины

### Проблема: после деплоя "ничего не поменялось"
Причина:
- Обновился image/pipeline-файл, но Function-код в `webui.db` остался старым.

Что делать:
- Проверить, откуда реально грузится A3 (Function vs pipeline).
- При Function-режиме синхронизировать запись в `webui.db`.

### Проблема: 500/503 после деплоя
Причина:
- Ошибка runtime (часто парсинг кода функции/битая запись в БД), а не build.

Что делать:
1. Смотреть runtime-логи (не только build logs).
2. При необходимости откатить ревизию в Amvera.

## 6) Правило изменений

- Перед выкладкой в прод всегда проверяется **тот же путь исполнения**, который используется в проде:
  - если прод работает через Function в `webui.db`, тестировать и синхронизировать именно этот путь.
- Не выкатывать изменения без локальной проверки ключевого сценария.

## 7) Быстрые команды

### Git
```powershell
git status
git add -A
git commit -m "..."
git push origin main
git push amvera main:master
```

### Локальная публикация
```powershell
.\publish.ps1
```

---

Если процесс деплоя меняется (например, полный переход на pipeline-only или автосинхронизацию Function), этот файл нужно обновить в первую очередь.

## Рабочая версия (зафиксировано)

- Baseline разработки: `74667d9`
- Рабочая версия для Amvera (на текущий момент): `74667d9`
- Проверка удалённых веток:
  - `origin/main` -> `74667d9`
  - `amvera/master` -> `74667d9`

### Правило безопасного выката

1. Не выкатывать в прод без явного согласования.
2. Перед выкладкой проверять локально ключевой сценарий.
3. После push в Amvera обязательно проверять хеш:

```powershell
git ls-remote origin refs/heads/main
git ls-remote amvera refs/heads/master
```

4. Для отката использовать конкретный хеш и проверку:

```powershell
git checkout <COMMIT_HASH>
git push amvera HEAD:master --force-with-lease
git ls-remote --refs amvera master
```


## Локальный snapshot для отката

- Локальная рабочая сборка (snapshot tag): `local-stable-2026-02-14`
- Локальный commit snapshot: `c0f0543`
- Назначение: быстрый возврат к текущей локально проверенной сборке.

## Локальный snapshot для отката (новая контрольная точка)

- Локальная рабочая сборка (snapshot tag): `local-stable-2026-02-14-2`
- Локальный commit snapshot: `917219e`
- Назначение: текущая контрольная точка после исправлений шага 6 и вывода анализа проекта.

Команда локального отката:
```powershell
git checkout local-stable-2026-02-14
```

Возврат на текущую ветку разработки:
```powershell
git checkout main
```

Откат к новой контрольной точке:
```powershell
git checkout local-stable-2026-02-14-2
```
