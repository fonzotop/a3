"""
Unit-тесты для a3_controller.py
Тестируем вспомогательные методы (parsing, validation, extraction)
"""

import pytest
import json
from pathlib import Path
import tempfile
import shutil
from unittest.mock import Mock, MagicMock, patch
import types
import sys

# Stub open_webui for unit tests
open_webui = types.ModuleType("open_webui")
open_webui.main = types.ModuleType("open_webui.main")

def _dummy_generate_chat_completions(*args, **kwargs):
    raise RuntimeError("LLM call not available in unit tests")

open_webui.main.generate_chat_completions = _dummy_generate_chat_completions
open_webui.models = types.ModuleType("open_webui.models")
open_webui.models.users = types.ModuleType("open_webui.models.users")

class _DummyUsers:
    @staticmethod
    def get_user_by_id(_):
        return None

open_webui.models.users.Users = _DummyUsers

sys.modules["open_webui"] = open_webui
sys.modules["open_webui.main"] = open_webui.main
sys.modules["open_webui.models"] = open_webui.models
sys.modules["open_webui.models.users"] = open_webui.models.users

# Импортируем класс, который тестируем
# Note: нужно адаптировать импорт под вашу структуру
sys.path.insert(0, str(Path(__file__).parent.parent))

from a3_assistant.pipe.a3_controller import Pipe


class TestPipeBasicMethods:
    """Тесты базовых методов класса Pipe"""

    @pytest.fixture
    def pipe(self):
        """Создаём экземпляр Pipe для тестирования"""
        return Pipe()

    # ========== Tests for parsing methods ==========

    def test_looks_like_one_sentence_valid(self, pipe):
        """Проверяем, что одно предложение распознаётся корректно"""
        assert pipe._looks_like_one_sentence("Это простое предложение.") is True
        assert pipe._looks_like_one_sentence("Ещё одно предложение") is True

    def test_looks_like_one_sentence_multiple(self, pipe):
        """Проверяем, что несколько предложений не проходят"""
        assert pipe._looks_like_one_sentence("Первое. Второе. Третье.") is False
        assert pipe._looks_like_one_sentence("Первое.\nВторое.\nТретье.") is False

    def test_looks_like_one_sentence_empty(self, pipe):
        """Пустая строка не должна пройти"""
        assert pipe._looks_like_one_sentence("") is False
        assert pipe._looks_like_one_sentence("   ") is False

    def test_contains_solution_language(self, pipe):
        """Проверяем детекцию слов решений"""
        assert pipe._contains_solution_language("надо автоматизировать") is True
        assert pipe._contains_solution_language("нужно оптимизировать") is True
        assert pipe._contains_solution_language("ВНЕДРИТЬ новое") is True
        assert pipe._contains_solution_language("Просто опишу проблему") is False

    def test_is_weak_field_check(self, pipe):
        """Проверяем детекцию слабых полей"""
        assert pipe._is_weak("пока неизвестно") is True
        assert pipe._is_weak("нет данных") is True
        assert pipe._is_weak("примерно 50%") is True
        assert pipe._is_weak("Точное значение: 1000") is False
        assert pipe._is_weak("") is True

    # ========== Tests for parsing choice numbers ==========

    def test_parse_choice_numbers_1_5_valid(self, pipe):
        """Правильный парсинг номеров 1-5"""
        assert pipe._parse_choice_numbers_1_5("1, 3, 5") == [1, 3, 5]
        assert pipe._parse_choice_numbers_1_5("1 и 2") == [1, 2]
        assert pipe._parse_choice_numbers_1_5("только 3") == [3]

    def test_parse_choice_numbers_1_5_empty(self, pipe):
        """Пустой или неверный ввод"""
        assert pipe._parse_choice_numbers_1_5("") == []
        assert pipe._parse_choice_numbers_1_5("a b c") == []

    def test_parse_choice_numbers_1_5_duplicates(self, pipe):
        """Дубликаты удаляются"""
        result = pipe._parse_choice_numbers_1_5("1, 1, 2, 2, 3")
        assert result == [1, 2, 3]

    def test_parse_choice_numbers_1_5_out_of_range(self, pipe):
        """Номера вне диапазона игнорируются"""
        result = pipe._parse_choice_numbers_1_5("1, 6, 7, 2")
        assert result == [1, 2]

    def test_parse_choice_numbers_1_6_valid(self, pipe):
        """Правильный парсинг номеров 1-6"""
        assert pipe._parse_choice_numbers_1_6("1, 3, 6") == [1, 3, 6]

    def test_parse_choice_numbers_1_6_out_of_range(self, pipe):
        """Номера вне диапазона 1-6"""
        result = pipe._parse_choice_numbers_1_6("1, 7, 8")
        assert result == [1]

    # ========== Tests for update variants command ==========

    def test_is_update_variants_cmd_english(self, pipe):
        """Проверяем команду обновления на английском"""
        assert pipe._is_update_variants_cmd("/regen") is True
        assert pipe._is_update_variants_cmd("regen") is True
        assert pipe._is_update_variants_cmd("r") is True

    def test_is_update_variants_cmd_russian(self, pipe):
        """Проверяем команду обновления на русском"""
        assert pipe._is_update_variants_cmd("обнови варианты") is True
        assert pipe._is_update_variants_cmd("обновить варианты") is True

    def test_is_update_variants_cmd_negative(self, pipe):
        """Случаи когда это не команда обновления"""
        assert pipe._is_update_variants_cmd("просто текст") is False
        assert pipe._is_update_variants_cmd("") is False

    # ========== Tests for step 2 field counting ==========

    def test_count_filled_and_strong_fields_step2_all_filled(self, pipe):
        """Все поля заполнены и сильные"""
        extracted = {
            "where_when": "В Москве, каждый день",
            "scale": "Средний",
            "consequences": "Потери времени",
            "who_suffers": "Команда разработки",
            "money_impact": "100 000 руб/месяц",
        }
        filled, strong, strong_list, weak_list = (
            pipe._count_filled_and_strong_fields_step2(extracted)
        )
        assert filled == 5
        assert strong == 5
        assert len(strong_list) == 5
        assert len(weak_list) == 0

    def test_count_filled_and_strong_fields_step2_weak_values(self, pipe):
        """Некоторые значения слабые"""
        extracted = {
            "where_when": "Не знаю где",
            "scale": "примерно",
            "consequences": "Потери времени",
            "who_suffers": "",
            "money_impact": "Данных нет",
        }
        filled, strong, strong_list, weak_list = (
            pipe._count_filled_and_strong_fields_step2(extracted)
        )
        assert filled == 4
        assert strong == 1
        assert "consequences" in strong_list

    def test_count_filled_and_strong_fields_step2_empty(self, pipe):
        """Все поля пустые"""
        extracted = {
            "where_when": "",
            "scale": "",
            "consequences": "",
            "who_suffers": "",
            "money_impact": "",
        }
        filled, strong, strong_list, weak_list = (
            pipe._count_filled_and_strong_fields_step2(extracted)
        )
        assert filled == 0
        assert strong == 0

    # ========== Tests for step 3 context check ==========

    def test_step3_context_ready_complete(self, pipe):
        """Контекст полностью готов"""
        ctx = {
            "start_event": "Начало процесса",
            "end_event": "Конец процесса",
            "owner": "Иван Петров",
            "perimeter": "Отдел закупок",
            "result_metrics": ["Метрика1", "Метрика2"],
        }
        ready, missing = pipe._step3_context_ready(ctx)
        assert ready is True
        assert missing == []

    def test_step3_context_ready_missing_fields(self, pipe):
        """Некоторые поля отсутствуют"""
        ctx = {
            "start_event": "Начало",
            "end_event": "",
            "owner": "",
            "perimeter": "Периметр",
            "result_metrics": ["Метрика1"],
        }
        ready, missing = pipe._step3_context_ready(ctx)
        assert ready is False
        assert "end_event" in missing
        assert "owner" in missing

    def test_step3_context_ready_insufficient_metrics(self, pipe):
        """Недостаточно метрик"""
        ctx = {
            "start_event": "Начало",
            "end_event": "Конец",
            "owner": "Владелец",
            "perimeter": "Периметр",
            "result_metrics": ["Только одна метрика"],
        }
        ready, missing = pipe._step3_context_ready(ctx)
        assert ready is False
        assert "result_metrics (>=2)" in missing

    # ========== Tests for metric extraction ==========

    def test_extract_custom_metrics_empty(self, pipe):
        """Пустой ввод"""
        result = pipe._extract_custom_metrics("")
        assert result == []

    def test_extract_custom_metrics_from_text(self, pipe):
        """Извлечение метрик из текста"""
        text = "Метрика: Время обработки\nМетрика: Качество"
        result = pipe._extract_custom_metrics(text)
        assert len(result) >= 1

    def test_dedupe_metrics_removes_duplicates(self, pipe):
        """Удаление дубликатов метрик"""
        items = [
            {"metric": "Время", "current_value": "5"},
            {"metric": "Время", "current_value": "10"},  # дубликат
            {"metric": "Качество", "current_value": "95%"},
        ]
        result = pipe._dedupe_metrics(items)
        assert len(result) == 2
        assert result[0]["metric"] == "Время"
        assert result[1]["metric"] == "Качество"

    def test_dedupe_metrics_empty(self, pipe):
        """Пустой список метрик"""
        result = pipe._dedupe_metrics([])
        assert result == []

    def test_parse_actions_template(self, pipe):
        text = "Контрмеры:\n- A\n- B"
        out = pipe._parse_actions_template(text)
        assert out == ["A", "B"]

    def test_parse_plan_items(self, pipe):
        text = (
            "Мероприятие: Do A\n"
            "Ожидаемый результат: Done\n"
            "Ответственный: Owner\n"
            "Срок: 2 weeks\n\n"
            "Мероприятие: Do B\n"
            "Ожидаемый результат: Done B\n"
            "Ответственный: Owner B\n"
            "Срок: 1 month"
        )
        out = pipe._parse_plan_items(text)
        assert len(out) == 2
        assert out[0]["action"] == "Do A"
        assert out[1]["owner"] == "Owner B"

    # ========== Tests for extraction methods ==========

    def test_extract_user_text_from_messages(self, pipe):
        """Извлечение текста из сообщений"""
        body = {
            "messages": [
                {"role": "user", "content": "Тестовое сообщение"}
            ]
        }
        text = pipe._extract_user_text(body)
        assert text == "Тестовое сообщение"

    def test_extract_user_text_from_prompt(self, pipe):
        """Извлечение текста из prompt"""
        body = {"prompt": "Прямой текст"}
        text = pipe._extract_user_text(body)
        assert text == "Прямой текст"

    def test_extract_user_text_from_content_list(self, pipe):
        """Извлечение текста из списка content"""
        body = {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Часть 1"},
                        {"type": "text", "text": "Часть 2"},
                    ],
                }
            ]
        }
        text = pipe._extract_user_text(body)
        assert "Часть 1" in text
        assert "Часть 2" in text

    def test_extract_user_text_empty(self, pipe):
        """Пустой ввод"""
        body = {}
        text = pipe._extract_user_text(body)
        assert text == ""

    def test_first_cmd_line_simple(self, pipe):
        """Извлечение первой командной строки"""
        text = "первая строка\nвторая строка"
        result = pipe._first_cmd_line(text)
        assert result == "первая строка"

    def test_first_cmd_line_empty(self, pipe):
        """Пустой текст"""
        result = pipe._first_cmd_line("")
        assert result == ""

    def test_first_cmd_line_regen_cmd(self, pipe):
        """Команда обновления варианов"""
        result = pipe._first_cmd_line("/regen\nкакой-то текст")
        assert result == "/regen"

    # ========== Tests for why-check extraction ==========

    def test_extract_why_check_valid_response(self, pipe):
        """Корректная проверка 'Почему'"""
        text = "причина контролируемо да нужно собрать"
        result = pipe._extract_why_check(text)
        assert result.get("classification") != ""
        assert result.get("controllable") != ""

    def test_extract_why_check_empty(self, pipe):
        """Пустой ввод"""
        result = pipe._extract_why_check("")
        assert result == {}

    # ========== Tests for root cause extraction ==========

    def test_extract_root_cause_fields_valid(self, pipe):
        """Корректное извлечение полей корневой причины"""
        text = """Корневая причина: Отсутствует стандарт
Тип: стандарт
Где в процессе: На этапе согласования
Управляемость: да
Что изменить: Создать SOP"""
        result = pipe._extract_root_cause_fields(text)
        assert result.get("root_cause") != ""
        assert result.get("type") != ""

    def test_extract_root_cause_fields_incomplete(self, pipe):
        """Неполный ввод"""
        text = """Корневая причина: Причина
Тип: стандарт"""
        result = pipe._extract_root_cause_fields(text)
        assert result.get("root_cause") != ""
        assert result.get("process_point") == ""

    # ========== Tests for JSON parsing ==========

    def test_safe_json_loads_valid(self, pipe):
        """Парсинг валидного JSON"""
        json_str = '{"key": "value"}'
        result = pipe._safe_json_loads(json_str)
        assert result == {"key": "value"}

    def test_safe_json_loads_with_markdown(self, pipe):
        """JSON с markdown маркерами"""
        json_str = '```json\n{"key": "value"}\n```'
        result = pipe._safe_json_loads(json_str)
        assert result == {"key": "value"}

    def test_safe_json_loads_with_bom(self, pipe):
        """JSON с BOM символом"""
        json_str = '﻿{"key": "value"}'
        result = pipe._safe_json_loads(json_str)
        assert result == {"key": "value"}

    def test_safe_json_loads_invalid(self, pipe):
        """Невалидный JSON"""
        with pytest.raises(ValueError):
            pipe._safe_json_loads("не json")

    def test_safe_json_loads_none(self, pipe):
        """None вместо строки"""
        with pytest.raises(ValueError):
            pipe._safe_json_loads(None)

    # ========== Tests for problem text cleaning ==========

    def test_clean_problem_text_with_markers(self, pipe):
        """Удаление маркеров начала строки"""
        assert pipe._clean_problem_text("* Проблема") == "Проблема"
        assert pipe._clean_problem_text("- Проблема") == "Проблема"
        assert pipe._clean_problem_text("? Проблема") == "Проблема"

    def test_clean_problem_text_with_bullet(self, pipe):
        """Удаление bullet point"""
        assert pipe._clean_problem_text("• Проблема") == "Проблема"

    def test_clean_problem_text_normal(self, pipe):
        """Обычный текст"""
        assert pipe._clean_problem_text("Обычная проблема") == "Обычная проблема"

    # ========== Tests for extract custom problem ==========

    def test_extract_custom_problem_from_template(self, pipe):
        """Извлечение проблемы из шаблона"""
        text = "проблема: Это наша проблема"
        result = pipe._extract_custom_problem(text)
        assert "наша проблема" in result

    def test_extract_custom_problem_plain_text(self, pipe):
        """Обычный текст как проблема"""
        text = "Это просто проблема"
        result = pipe._extract_custom_problem(text)
        assert "просто проблема" in result

    def test_extract_custom_problem_empty(self, pipe):
        """Пустой ввод"""
        result = pipe._extract_custom_problem("")
        assert result == ""

    def test_extract_custom_problem_regen_cmd(self, pipe):
        """Команда обновления как ввод"""
        result = pipe._extract_custom_problem("/regen")
        assert result == ""

    def test_extract_custom_problem_update_variants_ru(self, pipe):
        """Команда обновления вариантов на русском"""
        result = pipe._extract_custom_problem("обнови варианты")
        assert result == ""

    def test_extract_custom_problem_problem_prefix(self, pipe):
        """Проблема: ..."""
        result = pipe._extract_custom_problem("Проблема: Текст")
        assert "Текст" in result

    # ========== Tests for metric values parsing ==========

    def test_parse_metric_values_ordered_list(self, pipe):
        metrics = [
            {"metric": "A", "current_value": ""},
            {"metric": "B", "current_value": ""},
        ]
        text = "Значение: 10\nЗначение: 20"
        out = pipe._parse_metric_values(text, metrics, "current_value")
        assert out[0]["current_value"] == "10"
        assert out[1]["current_value"] == "20"

    def test_parse_metric_values_indexed(self, pipe):
        metrics = [
            {"metric": "A", "current_value": ""},
            {"metric": "B", "current_value": ""},
        ]
        text = "1) 5\n2) 9"
        out = pipe._parse_metric_values(text, metrics, "current_value")
        assert out[0]["current_value"] == "5"
        assert out[1]["current_value"] == "9"


class TestPipeWithTempFiles:
    """Тесты, требующие файловой системы"""

    @pytest.fixture
    def temp_dir(self):
        """Создание временной директории"""
        temp = tempfile.mkdtemp()
        yield temp
        shutil.rmtree(temp)

    @pytest.fixture
    def pipe_with_temp(self, temp_dir, monkeypatch):
        """Pipe с переопределёнными директориями"""
        pipe = Pipe()
        # Для этого теста нужно переопределить пути
        return pipe

    def test_state_path_generation(self, temp_dir, monkeypatch):
        """Проверка генерации пути состояния"""
        pipe = Pipe()
        path = pipe._state_path("A3-0001")
        assert "A3-0001.json" in str(path)

    def test_active_path_generation(self, temp_dir, monkeypatch):
        """Проверка генерации пути активного проекта"""
        pipe = Pipe()
        path = pipe._active_path("user-123")
        assert "user-123.json" in str(path)




class TestStep6EdgeCases:
    def _run_pipe(self, pipe, text, state, monkeypatch):
        import asyncio

        state_holder = {"state": state}

        def _load_state(_pid):
            return state_holder["state"]

        def _save_state(_pid, st):
            state_holder["state"] = st

        async def _problems(*args, **kwargs):
            return {"problems": ["P1", "P2", "P3", "P4"]}

        async def _whys(*args, **kwargs):
            return {"why_suggestions": ["W1", "W2", "W3"]}

        async def _hint(*args, **kwargs):
            return {"is_root": True, "reason": "test"}

        monkeypatch.setattr(pipe, "_load_state", _load_state)
        monkeypatch.setattr(pipe, "_save_state", _save_state)
        monkeypatch.setattr(pipe, "_get_step6_problem_proposals", _problems)
        monkeypatch.setattr(pipe, "_get_step6_why_suggestions", _whys)
        monkeypatch.setattr(pipe, "_get_step6_root_hint", _hint)
        monkeypatch.setattr(pipe, "_get_active_project", lambda _uid: "T-1")

        body = {"messages": [{"role": "user", "content": text}]}
        result = asyncio.run(pipe.pipe(body, {"id": "u1"}, None))
        return result, state_holder["state"]

    def test_step6_select_multiple(self, monkeypatch):
        pipe = Pipe()
        state = {
            "project_id": "T-1",
            "current_step": 6,
            "meta": {"step6_phase": "select_problem"},
            "data": {"steps": {"raw_problem": {"raw_problem_sentence": "Raw"}}},
        }
        msg, st = self._run_pipe(
            pipe,
            "Проблемы:\n- P1\n- P2\n- P3",
            state,
            monkeypatch,
        )
        assert "\u041f\u043e\u0447\u0435\u043c\u0443" in msg
        assert st["data"]["steps"]["step6_active_problem"]
        assert st["data"]["steps"]["step6_pending_problems"]

    def test_step6_select_custom_multiline(self, monkeypatch):
        pipe = Pipe()
        state = {
            "project_id": "T-1",
            "current_step": 6,
            "meta": {"step6_phase": "select_problem"},
            "data": {"steps": {"raw_problem": {"raw_problem_sentence": "Raw"}}},
        }
        msg, st = self._run_pipe(
            pipe,
            "\u041f\u0440\u043e\u0431\u043b\u0435\u043c\u0430: \u041c\u043e\u044f \u043f\u0440\u043e\u0431\u043b\u0435\u043c\u0430\n\u0435\u0449\u0435 \u0442\u0435\u043a\u0441\u0442",
            state,
            monkeypatch,
        )
        assert "\u041f\u043e\u0447\u0435\u043c\u0443" in msg
        assert st["data"]["steps"]["step6_active_problem"]

    def test_step6_empty_input_safe(self, monkeypatch):
        pipe = Pipe()
        state = {
            "project_id": "T-1",
            "current_step": 6,
            "meta": {"step6_phase": "select_problem"},
            "data": {"steps": {"raw_problem": {"raw_problem_sentence": "Raw"}}},
        }
        msg, st = self._run_pipe(pipe, "", state, monkeypatch)
        assert "\u0428\u0430\u0433" in msg or "\u0422\u0435\u043a\u0443\u0449\u0438\u0439 \u0448\u0430\u0433" in msg

    def test_step6_why_regen(self, monkeypatch):
        pipe = Pipe()
        state = {
            "project_id": "T-1",
            "current_step": 6,
            "meta": {"step6_phase": "why_loop"},
            "data": {
                "steps": {
                    "raw_problem": {"raw_problem_sentence": "Raw"},
                    "step6_active_problem": "P1",
                    "step6_why_chain": [],
                }
            },
        }
        msg, st = self._run_pipe(pipe, "\u043e\u0431\u043d\u043e\u0432\u0438 \u0432\u0430\u0440\u0438\u0430\u043d\u0442\u044b", state, monkeypatch)
        assert "\u0412\u0430\u0440\u0438\u0430\u043d\u0442\u044b" in msg

    def test_step6_why_ignores_problem_template(self, monkeypatch):
        pipe = Pipe()
        state = {
            "project_id": "T-1",
            "current_step": 6,
            "meta": {"step6_phase": "why_loop"},
            "data": {
                "steps": {
                    "raw_problem": {"raw_problem_sentence": "Raw"},
                    "step6_active_problem": "P1",
                    "step6_why_chain": [],
                }
            },
        }
        msg, st = self._run_pipe(
            pipe,
            "Проблемы:\n- P1\n- P2",
            state,
            monkeypatch,
        )
        assert "Почему?" in msg
        assert st["data"]["steps"]["step6_why_chain"] == []

    def test_step6_multiline_answer(self, monkeypatch):
        pipe = Pipe()
        state = {
            "project_id": "T-1",
            "current_step": 6,
            "meta": {"step6_phase": "why_loop"},
            "data": {
                "steps": {
                    "raw_problem": {"raw_problem_sentence": "Raw"},
                    "step6_active_problem": "P1",
                    "step6_why_chain": [],
                }
            },
        }
        msg, st = self._run_pipe(
            pipe,
            "Первая строка\nВторая строка",
            state,
            monkeypatch,
        )
        assert "Почему?" in msg
        chain = st["data"]["steps"]["step6_why_chain"]
        assert len(chain) == 1
        assert "Вторая строка" in chain[0]["answer"]

    def test_step6_mixed_format_answer(self, monkeypatch):
        pipe = Pipe()
        state = {
            "project_id": "T-1",
            "current_step": 6,
            "meta": {"step6_phase": "why_loop"},
            "data": {
                "steps": {
                    "raw_problem": {"raw_problem_sentence": "Raw"},
                    "step6_active_problem": "P1",
                    "step6_why_chain": [],
                }
            },
        }
        mixed = "Ответ:\n```\nСмешанный формат\n```"
        msg, st = self._run_pipe(pipe, mixed, state, monkeypatch)
        assert "Почему?" in msg
        chain = st["data"]["steps"]["step6_why_chain"]
        assert len(chain) == 1
        assert "Смешанный формат" in chain[0]["answer"]

    def test_step6_whitespace_input_safe(self, monkeypatch):
        pipe = Pipe()
        state = {
            "project_id": "T-1",
            "current_step": 6,
            "meta": {"step6_phase": "why_loop"},
            "data": {
                "steps": {
                    "raw_problem": {"raw_problem_sentence": "Raw"},
                    "step6_active_problem": "P1",
                    "step6_why_chain": [],
                }
            },
        }
        msg, st = self._run_pipe(pipe, "   \n  ", state, monkeypatch)
        assert "Почему?" in msg
        assert st["data"]["steps"]["step6_why_chain"] == []
class TestPipeIntegration:
    """Интеграционные тесты"""

    @pytest.fixture
    def pipe(self):
        return Pipe()

    def test_pipes_method(self, pipe):
        """Проверка метода pipes()"""
        pipes_list = pipe.pipes()
        assert isinstance(pipes_list, list)
        assert len(pipes_list) > 0
        assert "id" in pipes_list[0]
        assert pipes_list[0]["id"] == "a3"

    def test_valves_initialization(self, pipe):
        """Проверка инициализации Valves"""
        assert hasattr(pipe, "valves")
        assert pipe.valves.DEFAULT_PROJECT_ID == "A3-0001"
        assert pipe.valves.METHODOLOGIST_MODEL == "gpt-4o-mini"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
