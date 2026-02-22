# A3 MVP: Реальная логика работы и деплоя

Этот файл фиксирует, как проект **реально** работает в локалке и в проде (Amvera), где находится источник истины, и как выкатывать изменения без сюрпризов.

---

## 1) Ключевая архитектура

### 1.1 Источник истины — один файл

```
a3_assistant/pipe/a3_controller.py
```

Это единственный источник логики пайплайна. Все изменения вносятся только сюда.

### 1.2 Как код попадает в OpenWebUI

OpenWebUI берёт пайплайн из своей SQLite-базы (`webui.db`, таблица `function`, id = `a3_pm_methodologist`).
Синхронизация файла → БД выполняется скриптом `a3_assistant/scripts/sync_functions.py`.

**В проде (Amvera):** синк запускается автоматически при каждом старте контейнера через `a3_assistant/scripts/start_with_sync.sh`.
**Локально:** синк нужно запустить вручную после изменений (см. раздел 3).

### 1.3 Синхронизируемые функции

| id | Источник |
|----|----------|
| `a3_pm_methodologist` | `a3_assistant/pipe/a3_controller.py` |
| `a3_workflow_buttons` | `a3_assistant/actions/a3_workflow_buttons.py` |
| `smart_infographic` | `a3_assistant/actions/smart_infographic.py` |
| `export_to_word_enhanced_formatting` | `a3_assistant/actions/export_to_word_enhanced_formatting.py` |

### 1.4 Хранение данных проектов

Данные проектов хранятся в persist-смонтированном пути (переживает пересборки Amvera):

```
/app/backend/data/a3_state/projects/     # JSON-файлы проектов
/app/backend/data/a3_state/active_users/ # активный проект пользователя
```

---

## 2) Стандартный процесс изменений (dev → prod)

### Шаг 1. Изменить код

```
a3_assistant/pipe/a3_controller.py
```

### Шаг 2. Проверить локально

```bash
# Синхронизировать новый код в локальную webui.db
docker exec open-webui python3 -c "import subprocess; subprocess.run(['python', '/a3_assistant/scripts/sync_functions.py'])"

# Перезапустить контейнер, чтобы OpenWebUI перечитал функцию
docker compose restart
```

Проверить ключевой сценарий в локальном OpenWebUI (http://localhost:3000).

### Шаг 3. Коммит и пуш

```bash
git add a3_assistant/pipe/a3_controller.py  # и другие изменённые файлы
git commit -m "..."
git push origin main
git push amvera main
```

### Шаг 4. Amvera

После `git push amvera main` Amvera автоматически пересобирает контейнер.
При старте `start_with_sync.sh` запускает `sync_functions.py` — новый код загружается в `webui.db`.

Проверить runtime-логи и поведение в проде.

---

## 3) Проверка, что прод обновился

1. В логах сборки — актуальный коммит.
2. В runtime-логах — `[sync] webui.db function sync complete`.
3. В UI — поведение соответствует изменению.

---

## 4) Типовые проблемы

### После деплоя ничего не поменялось
- Проверить runtime-логи: синк прошёл или нет.
- Если синк упал — в логах будет `WARN: function sync failed`.

### Локально изменения не применились
- Запустить синк вручную (см. Шаг 2 выше).

### 500/503 после деплоя
- Смотреть runtime-логи (не build-логи).
- При необходимости откатить ревизию в Amvera.

---

## 5) Быстрые команды

### Git
```bash
git status
git add <файлы>
git commit -m "..."
git push origin main
git push amvera main
```

### Локальный синк без перезапуска
```bash
docker exec open-webui python3 -c "import subprocess; subprocess.run(['python', '/a3_assistant/scripts/sync_functions.py'])"
```

### Проверка remote-веток
```bash
git ls-remote origin refs/heads/main
git ls-remote amvera refs/heads/main
```

### Откат на конкретный коммит в Amvera
```bash
git checkout <COMMIT_HASH>
git push amvera HEAD:main --force-with-lease
```

---

## 6) Рабочие контрольные точки

| Дата | Commit | Описание |
|------|--------|----------|
| 2026-02-17 | `116e714` | UX workflow, автосоздание проектов |
| 2026-02-22 | `7618b66` | gpt-5.2, /edit команда, fix persist state, fix step7 IndexError |
| 2026-02-22 | `a38ebb5` | Улучшение форматирования всех шагов, команда /гипотеза, запрет англицизмов в LLM-промптах |

**Текущая рабочая версия:** `a38ebb5`
- `origin/main` → `a38ebb5`
- `amvera/main` → `a38ebb5`

---

## 7) Ключевые команды A3 в чате

| Команда | Действие |
|---------|----------|
| `/edit`, `/редактировать` | Редактирование данных проекта в чате |
| `/гипотеза` | Авто-черновик полного A3 по данным шага 1-3 (без сохранения) |
| `анализ проекта` | Полный отчёт по текущему проекту |
| `обнови варианты` | Новые LLM-подсказки для текущего шага |

**Модель:** `gpt-5.2` (valve `METHODOLOGIST_MODEL`)
