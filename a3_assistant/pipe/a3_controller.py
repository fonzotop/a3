from pathlib import Path

import json

import re as _re

from typing import List, Dict, Any, Tuple, Optional

from pydantic import BaseModel, Field

from open_webui.main import generate_chat_completions

from open_webui.models.users import Users

def _re_search(pattern, string, flags=0):

    try:

        return _re.search(pattern, string, flags)

    except _re.error:

        return None

def _re_match(pattern, string, flags=0):

    try:

        return _re.match(pattern, string, flags)

    except _re.error:

        return None

def _re_findall(pattern, string, flags=0):

    try:

        return _re.findall(pattern, string, flags)

    except _re.error:

        return []

def _re_split(pattern, string, maxsplit=0, flags=0):

    try:

        return _re.split(pattern, string, maxsplit=maxsplit, flags=flags)

    except _re.error:

        return [string]

def _re_fullmatch(pattern, string, flags=0):

    try:

        return _re.fullmatch(pattern, string, flags)

    except _re.error:

        return None

def _re_sub(pattern, repl, string, flags=0):

    try:

        return _re.sub(pattern, repl, string, flags=flags)

    except _re.error:

        return string

BASE_DIR = Path("/a3_assistant")

STATE_DIR = BASE_DIR / "state" / "projects"

ACTIVE_DIR = BASE_DIR / "state" / "active_users"

STEPS_DIR = BASE_DIR / "steps"

STATE_DIR.mkdir(parents=True, exist_ok=True)

ACTIVE_DIR.mkdir(parents=True, exist_ok=True)

# ====== DoD rules ======

SOLUTION_WORDS = [

    "автоматиз",

    "оптимиз",

    "внедр",

    "улучш",

    "реализ",

    "разработ",

    "настро",

    "создать",

    "ввести",

    "перейти",

    "сделать",

    "надо",

    "нужно",

]

WEAK_PHRASES = [

    "неизвестно",

    "пока неизвестно",

    "нет данных",

    "данных нет",

    "сложно сказать",

    "в целом",

    "примерно",

    "приблизительно",

    "не знаю",

    "пока нет",

    "нет информации",

    "не определено",

    "не могу сказать",

]

class Pipe:

    class Valves(BaseModel):

        DEFAULT_PROJECT_ID: str = Field(default="A3-0001")

        METHODOLOGIST_MODEL: str = Field(default="gpt-4o-mini")

    def __init__(self):

        self.valves = self.Valves()

    def pipes(self):
        return [{"id": "a3", "name": "A3 Project Controller"}]

    # ---------- paths ----------

    def _state_path(self, project_id: str) -> Path:

        return STATE_DIR / f"{project_id}.json"

    def _active_path(self, user_id: str) -> Path:

        return ACTIVE_DIR / f"{user_id}.json"

    # ---------- state ----------

    def _load_state(self, project_id: str) -> Dict[str, Any]:

        p = self._state_path(project_id)

        if not p.exists():

            return {"project_id": project_id, "current_step": 1, "meta": {}, "data": {}}

        return json.loads(p.read_text(encoding="utf-8-sig"))

    def _save_state(self, project_id: str, state: Dict[str, Any]) -> None:

        p = self._state_path(project_id)

        p.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---------- steps ----------

    def _load_step(self, step_id: int) -> Dict[str, Any]:

        p = STEPS_DIR / f"step_{step_id}.json"

        return json.loads(p.read_text(encoding="utf-8-sig"))

    def _step_exists(self, step_id: int) -> bool:

        return (STEPS_DIR / f"step_{step_id}.json").exists()

    # ---------- active project per user ----------

    def _get_active_project(self, user_id: str) -> str:

        p = self._active_path(user_id)

        if p.exists():

            try:

                data = json.loads(p.read_text(encoding="utf-8-sig"))

                pid = (data.get("project_id") or "").strip()

                if pid:

                    return pid

            except Exception:

                pass

        return self.valves.DEFAULT_PROJECT_ID

    def _set_active_project(self, user_id: str, project_id: str) -> None:

        p = self._active_path(user_id)

        p.write_text(

            json.dumps({"project_id": project_id}, ensure_ascii=False, indent=2),

            encoding="utf-8",

        )

    # ---------- commands ----------

    def _list_projects(self) -> List[str]:

        return [p.stem for p in STATE_DIR.glob("*.json") if p.is_file()]

    # ---------- extraction ----------

    def _extract_user_text(self, body: dict) -> str:

        msgs = body.get("messages") or []

        if not msgs:

            return (body.get("prompt") or "").strip()

        last = msgs[-1]

        content = last.get("content", "")

        if isinstance(content, str):

            return content.strip()

        if isinstance(content, list):

            parts = []

            for item in content:

                if isinstance(item, dict) and item.get("type") == "text":

                    parts.append(item.get("text", ""))

            return "\n".join(parts).strip()

        return ""

    def _first_cmd_line(self, text: str) -> str:
        if not text:
            return ""
        if self._is_update_variants_cmd(text):
            return ""
        cleaned = (
            (text or "")
            .replace("\ufeff", "")
            .replace("\u200b", "")
            .replace("\u200c", "")
            .replace("\u200d", "")
        )
        for line in cleaned.splitlines():
            line = line.strip()
            line = line.lstrip("*-•> ").strip()
            if line:
                return line
        return ""

    def _extract_llm_list(self, text: str) -> List[str]:
        if not text:
            return []
        raw = str(text)
        lines = [l.strip() for l in raw.splitlines() if l.strip()]
        cleaned: List[str] = []
        for l in lines:
            l = _re_sub(r"^\s*[-•\*\d\)\.]+\s*", "", l)
            if l:
                cleaned.append(l)
        return cleaned

    def _default_step2_hints(self, raw_problem: str) -> List[str]:
        hints = [
            "\u0413\u0434\u0435 \u0438 \u043a\u043e\u0433\u0434\u0430 \u043f\u0440\u043e\u044f\u0432\u043b\u044f\u0435\u0442\u0441\u044f \u043f\u0440\u043e\u0431\u043b\u0435\u043c\u0430 (\u0443\u0447\u0430\u0441\u0442\u043e\u043a, \u0441\u043c\u0435\u043d\u0430, \u043f\u0435\u0440\u0438\u043e\u0434)?",
            "\u041a\u0430\u043a\u043e\u0432 \u043c\u0430\u0441\u0448\u0442\u0430\u0431 (\u0441\u043a\u043e\u043b\u044c\u043a\u043e \u0441\u043b\u0443\u0447\u0430\u0435\u0432/\u0440\u0435\u0439\u0441\u043e\u0432/\u043e\u0431\u044a\u0435\u043a\u0442\u043e\u0432, \u043a\u0430\u043a \u0447\u0430\u0441\u0442\u043e)?",
            "\u041a\u0430\u043a\u0438\u0435 \u043f\u043e\u0441\u043b\u0435\u0434\u0441\u0442\u0432\u0438\u044f \u0434\u043b\u044f \u0441\u0440\u043e\u043a\u043e\u0432, \u043a\u0430\u0447\u0435\u0441\u0442\u0432\u0430 \u0438\u043b\u0438 \u0440\u0435\u043d\u0442\u0430\u0431\u0435\u043b\u044c\u043d\u043e\u0441\u0442\u0438?",
            "\u041a\u0442\u043e \u043a\u043e\u043d\u043a\u0440\u0435\u0442\u043d\u043e \u0441\u0442\u0440\u0430\u0434\u0430\u0435\u0442 \u043e\u0442 \u043f\u0440\u043e\u0431\u043b\u0435\u043c\u044b (\u0440\u043e\u043b\u0438/\u043f\u043e\u0434\u0440\u0430\u0437\u0434\u0435\u043b\u0435\u043d\u0438\u044f)?",
            "\u041a\u0430\u043a\u043e\u0435 \u0434\u0435\u043d\u0435\u0436\u043d\u043e\u0435 \u0432\u043b\u0438\u044f\u043d\u0438\u0435 (\u0443\u0431\u044b\u0442\u043a\u0438, \u043f\u0435\u0440\u0435\u0440\u0430\u0441\u0445\u043e\u0434, \u0443\u043f\u0443\u0449\u0435\u043d\u043d\u0430\u044f \u0432\u044b\u0433\u043e\u0434\u0430)?",
        ]
        return self._normalize_list(hints, limit=6)

    def _extract_step2_fields_local(self, user_text: str) -> Dict[str, str]:
        text = (user_text or "").replace("\r\n", "\n")
        lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
        out = {
            "where_when": "",
            "scale": "",
            "consequences": "",
            "who_suffers": "",
            "money_impact": "",
        }

        labels = {
            "где/когда": "where_when",
            "масштаб": "scale",
            "последствия": "consequences",
            "кто страдает": "who_suffers",
            "деньги": "money_impact",
        }

        for ln in lines:
            if ":" not in ln:
                continue
            left, right = ln.split(":", 1)
            key = left.strip().lower()
            val = right.strip()
            if key in labels and val:
                out[labels[key]] = val
        return out

    # ---------- helpers ----------

    def _contains_solution_language(self, text: str) -> bool:

        t = text.lower()

        return any(w in t for w in SOLUTION_WORDS)

    def _looks_like_one_sentence(self, text: str) -> bool:

        stripped = text.strip()

        if not stripped:

            return False

        if stripped.count("\n") >= 2:

            return False

        enders = _re_findall(r"[.!]", stripped)

        return len(enders) <= 2

    def _is_weak(self, value: str) -> bool:

        v = (value or "").strip().lower()

        if not v:

            return True

        return any(w in v for w in WEAK_PHRASES)

    def _count_filled_and_strong_fields_step2(

        self, extracted: Dict[str, str]

    ) -> Tuple[int, int, List[str], List[str]]:

        keys = ["where_when", "scale", "consequences", "who_suffers", "money_impact"]

        filled_count = 0

        strong_count = 0

        strong_fields: List[str] = []

        weak_fields: List[str] = []

        for k in keys:

            val = (extracted.get(k) or "").strip()

            if val:

                filled_count += 1

            if val and not self._is_weak(val):

                strong_count += 1

                strong_fields.append(k)

            else:

                weak_fields.append(k)

        return filled_count, strong_count, strong_fields, weak_fields

    def _step3_context_ready(self, ctx: Dict[str, Any]) -> Tuple[bool, List[str]]:

        missing = []

        if not (ctx.get("start_event") or "").strip():

            missing.append("start_event")

        if not (ctx.get("end_event") or "").strip():

            missing.append("end_event")

        if not (ctx.get("owner") or "").strip():

            missing.append("owner")

        if not (ctx.get("perimeter") or "").strip():

            missing.append("perimeter")

        metrics = ctx.get("result_metrics") or []

        if (

            not isinstance(metrics, list)

            or len([m for m in metrics if str(m).strip()]) < 2

        ):

            missing.append("result_metrics (>=2)")

        return (len(missing) == 0, missing)

    def _looks_like_step3_template(self, text: str) -> bool:

        t = (text or "").strip()

        if not t:

            return False

        t_low = t.lower()

        labels = [

            "событие начала",

            "событие окончания",

            "владелец процесса",

            "периметр",

            "метрики результата",

        ]

        hits = sum(1 for lab in labels if lab in t_low)

        if hits >= 2:

            return True

        colon_lines = [ln for ln in t.splitlines() if ":" in ln]

        if len(colon_lines) >= 3:

            return True

        return False

    def _parse_choice_2_and_B(

        self, user_text: str

    ) -> Tuple[Optional[int], Optional[str]]:

        t = (user_text or "").strip()

        if not t:

            return None, None

        m = _re_search(r"(?i)\b([1-5])\b.*\b([abc])\b", t)

        if not m:

            return None, None

        return int(m.group(1)), m.group(2).upper()

    def _parse_choice_numbers_1_5(self, user_text: str) -> List[int]:

        t = (user_text or "").strip()

        if not t:

            return []

        nums = _re_findall(r"\b([1-5])\b", t)

        out: List[int] = []

        for n in nums:

            v = int(n)

            if v not in out:

                out.append(v)

        return out

    def _parse_choice_numbers_1_6(self, user_text: str) -> List[int]:

        t = (user_text or "").strip()

        if not t:

            return []

        nums = _re_findall(r"\b([1-6])\b", t)

        out: List[int] = []

        for n in nums:

            v = int(n)

            if v not in out:

                out.append(v)

        return out

    def _extract_step3_context_fallback(self, user_text_step3: str) -> Dict[str, Any]:
        text = (user_text_step3 or "").strip()
        out = {
            "start_event": "",
            "end_event": "",
            "owner": "",
            "perimeter": "",
            "result_metrics": [],
        }
        if not text:
            return out

        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        colon_lines = [ln for ln in lines if ":" in ln]

        # Expected order by step template:
        # start_event, end_event, owner, perimeter, metrics.
        values: List[str] = []
        for ln in colon_lines[:5]:
            values.append(ln.split(":", 1)[1].strip())

        if len(values) > 0:
            out["start_event"] = values[0]
        if len(values) > 1:
            out["end_event"] = values[1]
        if len(values) > 2:
            out["owner"] = values[2]
        if len(values) > 3:
            out["perimeter"] = values[3]

        metric_tokens: List[str] = []
        if len(values) > 4:
            metric_tokens.extend(_re_split(r"[;,]", values[4]))

        # Also support bullet metrics on following lines.
        in_metrics_block = False
        for ln in lines:
            low = ln.lower()
            if ":" in ln and "метрик" in low:
                in_metrics_block = True
                continue
            if in_metrics_block:
                token = ln.lstrip("-*• ").strip()
                if token:
                    metric_tokens.append(token)
                elif ":" in ln:
                    break

        out["result_metrics"] = [m.strip() for m in metric_tokens if m.strip()][:4]
        return out

    def _fallback_step3_proposals(
        self, raw_problem: str, process_context: dict
    ) -> Dict[str, Any]:
        start_event = (process_context.get("start_event") or "").strip()
        end_event = (process_context.get("end_event") or "").strip()
        perimeter = (process_context.get("perimeter") or "").strip()
        metrics = process_context.get("result_metrics") or []
        metric_1 = str(metrics[0]).strip() if isinstance(metrics, list) and metrics else ""
        metric_2 = str(metrics[1]).strip() if isinstance(metrics, list) and len(metrics) > 1 else ""

        process_base = []
        if start_event and end_event:
            process_base.append(f"От {start_event} до {end_event}")
        if perimeter:
            process_base.append(f"в контуре {perimeter}")
        flow_hint = " ".join(process_base).strip() or (raw_problem or "ключевого процесса")

        process_variants = [
            f"Планирование и исполнение процесса {flow_hint}",
            f"Координация и контроль процесса {flow_hint}",
            f"Организация работ и закрытие цикла {flow_hint}",
            f"Сквозной процесс выполнения работ {flow_hint}",
            f"Подготовка, исполнение и завершение процесса {flow_hint}",
        ]

        project_variants = [
            f"Снижение потерь в процессе {flow_hint}",
            f"Оптимизация процесса {flow_hint}",
            "Повышение предсказуемости и управляемости процесса",
        ]
        if metric_1:
            project_variants[0] = f"Улучшение показателя: {metric_1}"
        if metric_2:
            project_variants[1] = f"Стабилизация показателя: {metric_2}"

        return {"process_variants": process_variants[:5], "project_variants": project_variants[:3]}

    def _is_update_variants_cmd(self, text: str) -> bool:

        t = (text or "").strip().lower()

        if t in {"/regen", "regen", "r"}:

            return True

        def _codes(s: str) -> list:

            return [ord(c) for c in s]

        # "обнови варианты"

        if _codes(t) == [1086, 1073, 1085, 1086, 1074, 1080, 32, 1074, 1072, 1088, 1080, 1072, 1085, 1090, 1099]:

            return True

        # "обновить варианты"

        if _codes(t) == [1086, 1073, 1085, 1086, 1074, 1080, 1090, 1100, 32, 1074, 1072, 1088, 1080, 1072, 1085, 1090, 1099]:

            return True

        return False

    def _extract_custom_metrics(self, user_text: str) -> List[Dict[str, str]]:

        text = (user_text or "").strip()

        if not text:

            return []

        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

        results: List[Dict[str, str]] = []

        i = 0

        while i < len(lines):

            line = lines[i]

            low = line.lower()

            if low.startswith("метрика:"):
                name = line.split(":", 1)[1].strip()

                value = ""

                if i + 1 < len(lines):

                    next_line = lines[i + 1]

                    next_low = next_line.lower()

                    if next_low.startswith("текущее значение:") or next_low.startswith("значение:"):

                        value = next_line.split(":", 1)[1].strip()

                        i += 1

                if name:

                    results.append({"metric": name, "current_value": value})

            i += 1

        if results:

            return results

        candidates: List[str] = []

        for part in _re_split(r"[;\n]", text):

            t = part.strip().strip("-?*")

            if not t:

                continue

            if _re_fullmatch(r"[1-5](\s*[,:]\s*[1-5])+", t) or _re_fullmatch(r"[1-5]", t):

                continue

            if _re_search(r"(?i)обнови\s+варианты", t):

                continue

            if _re_search(r"(?i)текущее\s+значение", t):

                continue

            candidates.append(t)

        return [{"metric": c, "current_value": ""} for c in candidates]

    def _parse_metrics_template(self, text_in: str) -> List[str]:
        def _clean_line(s: str) -> str:
            return (
                (s or "")
                .replace("\ufeff", "")
                .replace("\u200b", "")
                .replace("\u200c", "")
                .replace("\u200d", "")
                .strip()
            )

        lines = [_clean_line(ln) for ln in (text_in or "").splitlines()]
        lines = [ln for ln in lines if ln]
        if not lines:
            return []
        head = lines[0].lower()
        if not head.startswith("метрики:"):

            return []

        items = []

        tail = head.split(":", 1)[1].strip()

        if tail:

            items.append(tail)

        for ln in lines[1:]:

            ln = ln.lstrip("-•*").strip()

            if ln:

                items.append(ln)

        return [i for i in items if i]

    def _dedupe_metrics(self, items: List[Dict[str, str]]) -> List[Dict[str, str]]:
        if not isinstance(items, list):
            return []
        seen = set()
        out: List[Dict[str, str]] = []
        for it in items:

            name = (it.get("metric") or "").strip()

            if not name:

                continue

            key = name.lower()

            if key in seen:

                continue

            seen.add(key)

            out.append(

                {

                    "metric": name,

                    "current_value": (it.get("current_value") or "").strip(),

                }

            )

        return out

    def _normalize_list(self, items, limit=10) -> List[str]:
        if not isinstance(items, list):
            return []
        out = []
        for x in items:
            s = str(x).strip()
            if s:
                out.append(s)
        return out[:limit]

    def _parse_actions_template(self, text_in: str) -> List[str]:
        def _clean_line(s: str) -> str:
            return (
                (s or "")
                .replace("\ufeff", "")
                .replace("\u200b", "")
                .replace("\u200c", "")
                .replace("\u200d", "")
                .strip()
            )

        def _is_actions_header(head: str) -> bool:
            h = (head or "").strip().lower()
            if h.startswith("контрмеры:") or h.startswith("контрмеры"):
                return True
            # fallback by codepoints: "контрмеры"
            target = [1082, 1086, 1085, 1090, 1088, 1084, 1077, 1088, 1099]
            codes = [ord(c) for c in h if c not in [":", " "]]
            if codes[: len(target)] == target:
                return True
            return False

        lines = [_clean_line(ln) for ln in (text_in or "").splitlines()]
        lines = [ln for ln in lines if ln]
        if not lines:
            return []
        head = lines[0].lower()
        if not _is_actions_header(head):
            return []
        items = []
        tail = ""
        if ":" in head:
            tail = head.split(":", 1)[1].strip()
        if tail:
            items.append(tail)
        for ln in lines[1:]:
            ln = ln.lstrip("-•*").strip()
            if ln:
                items.append(ln)
        return [i for i in items if i]

    def _parse_plan_items(self, text_in: str) -> List[Dict[str, str]]:
        lines = [ln.strip() for ln in (text_in or "").splitlines() if ln.strip()]
        if not lines:
            return []
        items: List[Dict[str, str]] = []
        current: Dict[str, str] = {}

        def _flush():
            if current:
                items.append(current.copy())
                current.clear()

        for ln in lines:
            low = ln.lower()
            if low.startswith("мероприятие:"):
                _flush()
                current["action"] = ln.split(":", 1)[1].strip()
            elif low.startswith("ожидаемый результат:"):
                current["expected_result"] = ln.split(":", 1)[1].strip()
            elif low.startswith("ответственный:"):
                current["owner"] = ln.split(":", 1)[1].strip()
            elif low.startswith("срок:"):
                current["due"] = ln.split(":", 1)[1].strip()
        _flush()

        # sanitize
        out = []
        for it in items:
            action = (it.get("action") or "").strip()
            if not action:
                continue
            out.append(
                {
                    "action": action,
                    "expected_result": (it.get("expected_result") or "").strip(),
                    "owner": (it.get("owner") or "").strip(),
                    "due": (it.get("due") or "").strip(),
                }
            )
        return out

    def _parse_metric_values(

        self, user_text: str, metrics: List[Dict[str, str]], value_key: str

    ) -> List[Dict[str, str]]:

        if not isinstance(metrics, list):

            return []

        text = (user_text or "").strip()

        if not text:

            return metrics

        def _clean(s: str) -> str:

            return (

                (s or "")

                .replace("﻿", "")

                .replace("​", "")

                .replace("‌", "")

                .replace("‍", "")

                .replace(" ", " ")

                .strip()

            )

        label_metric = "метрика"

        label_value_current = "текущее"

        label_value_target = "целевое"

        label_value = "значение"

        lines = [_clean(ln) for ln in text.splitlines() if _clean(ln)]

        name_to_idx = {

            _clean(m.get("metric") or "").lower(): i for i, m in enumerate(metrics)

        }

        out = [dict(m) for m in metrics]

        current_metric = ""

        ordered_values = []

        for line in lines:

            low = line.lower()

            if low.startswith(label_metric + ":"):

                current_metric = _clean(line.split(":", 1)[1])

                continue

            if low.startswith(label_value_current + " " + label_value + ":") or low.startswith(label_value_target + " " + label_value + ":") or low.startswith(label_value + ":"):

                value = _clean(line.split(":", 1)[1])

                if value:

                    ordered_values.append(value)

                if current_metric and current_metric.lower() in name_to_idx and value:

                    out[name_to_idx[current_metric.lower()]][value_key] = value

                continue

            m = _re_match(r"^\s*([1-9])[\):.\-]\s*(.+)$", line)

            if m:

                idx = int(m.group(1)) - 1

                if 0 <= idx < len(out):

                    out[idx][value_key] = _clean(m.group(2))

        missing_idxs = [i for i, m in enumerate(out) if not _clean(m.get(value_key))]

        if ordered_values and len(ordered_values) == len(out):

            for i, val in enumerate(ordered_values):

                out[i][value_key] = val

        elif ordered_values and missing_idxs:

            for idx, val in zip(missing_idxs, ordered_values):

                out[idx][value_key] = val

        return out

    def _extract_custom_problem(self, user_text: str) -> str:
        text = (
            (user_text or "")
            .replace("\ufeff", "")
            .replace("\u200b", "")
            .replace("\u200c", "")
            .replace("\u200d", "")
            .strip()
        )
        if not text:
            return ""
        if self._is_update_variants_cmd(text):

            return ""

        label_problem = "".join(

            chr(c) for c in [1087, 1088, 1086, 1073, 1083, 1077, 1084, 1072]

        )

        low = text.lower()

        if low.startswith(label_problem + ":"):

            return text.split(":", 1)[1].strip()

        return text.strip()

    def _clean_problem_text(self, text: str) -> str:

        t = (text or "").strip()

        if t.startswith(("*", "-", "?")):

            t = t.lstrip("*-?").strip()

        if t.startswith("\u2022"):

            t = t.lstrip("\u2022").strip()

        return t

    def _extract_root_cause_fields(self, user_text: str) -> dict:

        text = (user_text or "").strip()

        if not text:

            return {}

        labels = {

            "root_cause": "".join(

                chr(c)

                for c in [

                    1082,

                    1086,

                    1088,

                    1085,

                    1077,

                    1074,

                    1072,

                    1103,

                    32,

                    1087,

                    1088,

                    1080,

                    1095,

                    1080,

                    1085,

                    1072,

                ]

            ),

            "type": "".join(chr(c) for c in [1090, 1080, 1087]),

            "process_point": "".join(

                chr(c)

                for c in [

                    1075,

                    1076,

                    1077,

                    32,

                    1074,

                    32,

                    1087,

                    1088,

                    1086,

                    1094,

                    1077,

                    1089,

                    1089,

                    1077,

                ]

            ),

            "controllable": "".join(

                chr(c)

                for c in [

                    1091,

                    1087,

                    1088,

                    1072,

                    1074,

                    1083,

                    1103,

                    1077,

                    1084,

                    1086,

                    1089,

                    1090,

                    1100,

                ]

            ),

            "change_hint": "".join(

                chr(c)

                for c in [1095, 1090, 1086, 32, 1080, 1079, 1084, 1077, 1085, 1080, 1090, 1100]

            ),

        }

        result = {k: "" for k in labels}

        for raw_line in text.splitlines():

            line = raw_line.strip()

            if not line:

                continue

            low = line.lower()

            for key, label in labels.items():

                if low.startswith(label + ":"):

                    result[key] = line.split(":", 1)[1].strip()

        return result

    def _extract_why_check(self, user_text: str) -> dict:

        text = (user_text or "").strip().lower()

        if not text:

            return {}

        tokens = {

            "cause": "".join(chr(c) for c in [1087, 1088, 1080, 1095, 1080, 1085, 1072]),

            "symptom": "".join(chr(c) for c in [1089, 1080, 1084, 1087, 1090, 1086, 1084]),

            "unsure": "".join(chr(c) for c in [1085, 1077, 32, 1091, 1074, 1077, 1088, 1077, 1085]),

            "yes": "".join(chr(c) for c in [1076, 1072]),

            "partly": "".join(chr(c) for c in [1095, 1072, 1089, 1090, 1080, 1095, 1085, 1086]),

            "no": "".join(chr(c) for c in [1085, 1077, 1090]),

            "need_data": "".join(chr(c) for c in [1085, 1091, 1078, 1085, 1086, 32, 1089, 1086, 1073, 1088, 1072, 1090, 1100]),

        }

        def _pick(options):

            for opt in options:

                if opt and opt in text:

                    return opt

            return ""

        classification = _pick([tokens["cause"], tokens["symptom"], tokens["unsure"]])

        controllable = _pick([tokens["yes"], tokens["partly"], tokens["no"]])

        eliminates = _pick([tokens["yes"], tokens["partly"], tokens["unsure"]])

        evidence = _pick([tokens["yes"], tokens["no"], tokens["need_data"]])

        return {

            "classification": classification,

            "controllable": controllable,

            "eliminates_problem": eliminates,

            "evidence": evidence,

        }

    def _safe_json_loads(self, content: str) -> dict:

        if content is None:

            raise ValueError("Empty LLM content (None)")

        s = str(content).strip().lstrip("???")

        if not s:

            raise ValueError("Empty LLM content (blank)")

        s = _re_sub(r"^\s*```(?:json)?\s*", "", s, flags=_re.IGNORECASE)

        s = _re_sub(r"\s*```\s*$", "", s)

        try:

            return json.loads(s)

        except Exception:

            pass

        m = _re_search(r"\{.*\}", s, flags=_re.DOTALL)

        if m:

            return json.loads(m.group(0).strip())

        raise ValueError("LLM did not return valid JSON")

# ---------- LLM ----------

    def _model_candidates(self) -> List[str]:
        candidates = [
            (self.valves.METHODOLOGIST_MODEL or "").strip(),
            "gpt-4o-mini",
            "gpt-4o",
            "gpt-4.1-mini",
        ]
        out: List[str] = []
        seen = set()
        for m in candidates:
            if not m or m in seen:
                continue
            seen.add(m)
            out.append(m)
        return out

    def _step6_why_fallback(self, effect: str) -> List[str]:
        e = (effect or "").strip()
        el = e.lower()
        out: List[str] = []

        def add(items: List[str]) -> None:
            for item in items:
                t = (item or "").strip()
                if t and t not in out:
                    out.append(t)

        # Domain-specific hints for road construction logistics.
        if any(k in el for k in ["грузоперев", "перевоз", "асфальтобетон", "смес"]):
            add(
                [
                    "Планирование рейсов выполняется без актуальных данных по потребности и графику укладки.",
                    "Маршруты и загрузка транспорта не оптимизированы, из-за чего растет доля холостых пробегов.",
                    "Фактическое время простоев на погрузке и выгрузке не контролируется и не анализируется.",
                    "Тарифы и условия перевозки пересматриваются нерегулярно и не привязаны к рыночным изменениям.",
                    "Нет единого владельца процесса, который отвечает за стоимость перевозок по всей цепочке.",
                ]
            )

        if any(k in el for k in ["стоим", "затрат", "расход", "рентабель"]):
            add(
                [
                    "Нормативы затрат на перевозку не обновлены под текущие условия проекта.",
                    "Отклонения факта от плана выявляются поздно, и корректирующие действия запускаются с задержкой.",
                    "Часть затрат учитывается постфактум, поэтому управленческие решения принимаются на неполных данных.",
                ]
            )

        if not out:
            add(
                [
                    "На входе процесса отсутствуют единые правила и критерии планирования работ.",
                    "Ответственность между участниками процесса распределена нечетко, из-за чего решения запаздывают.",
                    "Контрольные точки процесса определены формально и не предотвращают отклонения.",
                    "Данные для управления процессом собираются несвоевременно и не в полном объеме.",
                    "Причины отклонений фиксируются нерегулярно, поэтому ошибки повторяются.",
                ]
            )

        return self._normalize_list(out, limit=5)

    def _step7_countermeasure_fallback(self, root_cause: str) -> List[str]:
        rc = (root_cause or "").lower()
        out: List[str] = []

        def add(items: List[str]) -> None:
            for item in items:
                txt = (item or "").strip()
                if txt and txt not in out:
                    out.append(txt)

        if any(k in rc for k in ["данн", "учет", "точност", "прогноз"]):
            add(
                [
                    "Ввести единый шаблон сбора данных по перевозкам и обязательные поля.",
                    "Назначить владельца качества данных и регламент проверки перед расчетом.",
                    "Настроить контроль полноты данных с еженедельным разбором пропусков.",
                    "Устранить дублирование источников данных и определить единый источник истины.",
                    "Автоматизировать загрузку данных из учетной системы в расчетные формы.",
                ]
            )
        if any(k in rc for k in ["соглас", "роль", "ответствен", "координац"]):
            add(
                [
                    "Утвердить RACI по процессу согласования и передачи ведомостей.",
                    "Зафиксировать SLA по срокам согласования между участниками процесса.",
                    "Ввести ежедневный короткий статус по просроченным согласованиям.",
                    "Определить маршрут эскалации при нарушении сроков.",
                ]
            )
        if any(k in rc for k in ["срок", "задерж", "опоздан", "время"]):
            add(
                [
                    "Ввести контрольные точки сроков на каждом этапе процесса.",
                    "Определить допустимые отклонения и правила приоритизации задач.",
                    "Настроить автоматические напоминания по приближению дедлайна.",
                    "Проводить еженедельный анализ причин задержек и корректирующие действия.",
                ]
            )
        if not out:
            add(
                [
                    "Утвердить стандарт выполнения процесса с понятными шагами и сроками.",
                    "Назначить ответственных по этапам и правилам передачи результата.",
                    "Ввести регулярный контроль исполнения и разбор отклонений.",
                    "Обновить инструкции и провести обучение участников процесса.",
                    "Автоматизировать критичные точки контроля данных и сроков.",
                ]
            )
        return self._normalize_list(out, limit=5)

    async def _chat_once_with_fallback(
        self, __request__, __user__: dict, messages: List[Dict[str, Any]]
    ) -> Tuple[str, str]:
        uid = (__user__ or {}).get("id") if isinstance(__user__, dict) else None
        user = Users.get_user_by_id(uid) if uid else None
        call_user = user or (__user__ if isinstance(__user__, dict) else {"id": "system"})
        errs: List[str] = []
        for model_name in self._model_candidates():
            try:
                result = await generate_chat_completions(
                    request=__request__,
                    form_data={
                        "model": model_name,
                        "messages": messages,
                        "stream": False,
                    },
                    user=call_user,
                )
                if not isinstance(result, dict):
                    raise ValueError(f"bad_llm_result_type={type(result).__name__}")
                choices = result.get("choices")
                if not isinstance(choices, list) or not choices:
                    raise ValueError("bad_llm_result_choices")
                first = choices[0] if isinstance(choices[0], dict) else {}
                message = first.get("message") if isinstance(first, dict) else {}
                if not isinstance(message, dict):
                    raise ValueError("bad_llm_result_message")
                content = message.get("content")
                if content is None:
                    raise ValueError("empty_llm_content")
                return (content or ""), model_name
            except Exception as e:
                errs.append(f"{model_name}: {e}")
                continue
        raise ValueError("; ".join(errs) if errs else "No available model")

    async def _call_llm_json(

        self, __request__, __user__: dict, messages: List[Dict[str, Any]]

    ) -> Dict[str, Any]:

        last_err = None

        last_content = ""

        for _ in range(2):

            content, _ = await self._chat_once_with_fallback(__request__, __user__, messages)

            last_content = (content or "").strip().lstrip("\ufeff")

            try:

                return self._safe_json_loads(last_content)

            except Exception as e:

                last_err = e

                messages = messages + [

                    {

                        "role": "user",

                        "content": "Верни только валидный JSON. Без пояснений, без markdown и без ```.",

                    }

                ]

        snippet = (

            (last_content[:200] + "...") if len(last_content) > 200 else last_content

        )

        raise ValueError(f"{last_err}. LLM content snippet: {snippet}")

    async def _get_step2_hints_and_extract(

        self,

        __request__,

        __user__: dict,

        raw_problem: str,

        user_text_step2: str,

    ) -> Dict[str, Any]:

        system = (

            "Ты методолог A3/Lean в дорожно-строительной отрасли. "

            "Помогаешь конкретизировать проблему (As-Is) без поиска причин и без предложений решений. "

            "Нужны 5 полей: где/когда, масштаб, последствия, кто страдает, деньги (оценочно). "

            "Верни СТРОГО JSON."

        )

        user_prompt = (

            "Сгенерируй контекстные подсказки для шага 2 и (если есть текст пользователя на шаге 2) извлеки поля.\n"

            "Если текста шага 2 нет — оставь extracted пустыми строками, но hints всё равно сформируй.\n\n"

            "Формат ответа (строго JSON):\n"

            "{\n"

            '  "extracted": {\n'

            '    "where_when": "",\n'

            '    "scale": "",\n'

            '    "consequences": "",\n'

            '    "who_suffers": "",\n'

            '    "money_impact": ""\n'

            "  },\n"

            '  "hints": ["...", "...", "...", "..."]\n'

            "}\n\n"

            f"Сырая проблема (шаг 1): {raw_problem}\n"

            f"Текст пользователя (шаг 2, может быть пустым): {user_text_step2}"

        )

        data = await self._call_llm_json(

            __request__,

            __user__,

            [

                {"role": "system", "content": system},

                {"role": "user", "content": user_prompt},

            ],

        )

        extracted = data.get("extracted") or {}

        hints = self._normalize_list(data.get("hints") or [], limit=6)
        if not hints:
            hints = self._default_step2_hints(raw_problem)

        extracted_norm = {

            "where_when": (extracted.get("where_when") or "").strip(),

            "scale": (extracted.get("scale") or "").strip(),

            "consequences": (extracted.get("consequences") or "").strip(),

            "who_suffers": (extracted.get("who_suffers") or "").strip(),

            "money_impact": (extracted.get("money_impact") or "").strip(),

        }

        return {"extracted": extracted_norm, "hints": hints}

    async def _get_step3_context_hints_examples_and_extract(

        self,

        __request__,

        __user__: dict,

        raw_problem: str,

        problem_spec: dict,

        user_text_step3: str,

    ) -> Dict[str, Any]:

        system = (

            "Ты методолог A3/BPM в дорожно-строительной отрасли. "

            "Твоя задача — помочь зафиксировать КОНТЕКСТ процесса, где существует проблема. "

            "НЕ предлагай решения и автоматизацию. НЕ выбирай название процесса и проекта. "

            "Нужны: событие начала, событие окончания, владелец, периметр, метрики результата (без чисел). "

            "Отвечай ТОЛЬКО на русском языке. Верни СТРОГО JSON."

        )

        user_prompt = (
            "1) Сформируй подсказки (hints) по заполнению полей шага 3.\n"
            "2) Дай примеры (examples) ПРЯМО под текущий контекст (по проблеме/конкретизации).\n"
            "3) Предложи 5 метрик результата (metric_suggestions) — отраслевые/процессные, без чисел.\n"
            "4) Если есть текст пользователя — извлеки поля в extracted.\n"
            "Если текста нет — extracted оставь пустыми значениями, но hints/examples/metric_suggestions всё равно заполни.\n\n"
            "Примеры для периметра могут включать: генеральный директор, главный инженер, заместитель ГД по производству, "
            "заместитель ГД по обеспечению производства, отдел геодезии, строительная лаборатория, "
            "производственно-технический отдел, дорожно-строительный участок, начальник участка, старший прораб, "
            "финансово-экономический отдел, бухгалтерия, отдел кадров, заместитель ГД по развитию производственной системы, "
            "заместитель ГД по экономике и финансам, отдел главного механика, служба охраны труда и ООС, "
            "отдел главного энергетика, отдел материально-технического обеспечения, заказчик (производственная компания).\n\n"
            "Формат ответа (строго JSON):\n"
            "{\n"
            '  "extracted": {\n'
            '    "start_event": "",\n'

            '    "end_event": "",\n'

            '    "owner": "",\n'

            '    "perimeter": "",\n'

            '    "result_metrics": []\n'

            "  },\n"

            '  "hints": ["...","...","...","..."],\n'

            '  "examples": {\n'

            '    "start_event": ["...","..."],\n'

            '    "end_event": ["...","..."],\n'

            '    "owner": ["...","..."],\n'

            '    "perimeter": ["...","..."]\n'

            "  },\n"

            '  "metric_suggestions": ["...","...","...","...","..."]\n'

            "}\n\n"

            f"Сырая проблема: {raw_problem}\n"

            f"Конкретизация проблемы (шаг 2): {problem_spec}\n"

            f"Текст пользователя (шаг 3, может быть пустым): {user_text_step3}"

        )

        try:
            data = await self._call_llm_json(
                __request__,
                __user__,
                [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_prompt},
                ],
            )
        except Exception:
            data = {
                "extracted": self._extract_step3_context_fallback(user_text_step3),
                "hints": [],
                "examples": {},
                "metric_suggestions": [],
            }

        extracted = data.get("extracted") or {}

        hints = data.get("hints") or []

        examples = data.get("examples") or {}

        metric_suggestions = data.get("metric_suggestions") or []

        start_event = (extracted.get("start_event") or "").strip()

        end_event = (extracted.get("end_event") or "").strip()

        owner = (extracted.get("owner") or "").strip()

        perimeter = (extracted.get("perimeter") or "").strip()

        metrics = extracted.get("result_metrics") or []

        if isinstance(metrics, list):

            metrics = [str(x).strip() for x in metrics if str(x).strip()]

        else:

            metrics = []

        def _norm_list(v) -> List[str]:

            if isinstance(v, list):

                return [str(x).strip() for x in v if str(x).strip()]

            return []

        examples_norm = {

            "start_event": _norm_list(examples.get("start_event")),

            "end_event": _norm_list(examples.get("end_event")),

            "owner": _norm_list(examples.get("owner")),

            "perimeter": _norm_list(examples.get("perimeter")),

        }

        if isinstance(metric_suggestions, list):

            metric_suggestions = [

                str(x).strip() for x in metric_suggestions if str(x).strip()

            ]

        else:

            metric_suggestions = []

        metric_suggestions = metric_suggestions[:5]

        # --- language safety: ensure Russian output ---

        def _count_cyr(s: str) -> int:

            return sum(1 for ch in s if "а" <= ch.lower() <= "я" or ch.lower() == "ё")

        def _count_lat(s: str) -> int:

            return sum(1 for ch in s if "a" <= ch.lower() <= "z")

        combined_text = " ".join(

            [

                " ".join(hints),

                " ".join(sum(examples_norm.values(), [])),

                " ".join(metric_suggestions),

            ]

        )

        if _count_lat(combined_text) > _count_cyr(combined_text):

            hints = [

                "Укажите событие, которое инициирует процесс.",

                "Опишите событие, которое завершает процесс.",

                "Назовите владельца процесса (роль/ответственный).",

                "Опишите периметр: какие подразделения и участки вовлечены.",

                "Перечислите 2–4 метрики результата без чисел.",

            ]

            examples_norm = {
                "start_event": [
                    "Получение запроса на подготовку ведомостей",
                    "Начало отчетного периода по списанию материалов",
                ],
                "end_event": [
                    "Согласование ведомостей ответственным лицом",
                    "Передача ведомостей в бухгалтерию",
                ],
                "owner": [
                    "Руководитель участка",
                    "Ответственный за материально-техническое обеспечение",
                ],
                "perimeter": [
                    "Генеральный директор",
                    "Главный инженер",
                    "Производственно-технический отдел",
                    "Строительная лаборатория",
                    "Финансово-экономический отдел",
                    "Бухгалтерия",
                    "Старший прораб",
                    "Отдел главного механика",
                    "Отдел главного энергетика",
                    "Отдел материально-технического обеспечения",
                ],
            }
            metric_suggestions = [

                "Своевременность предоставления ведомостей",

                "Количество исправлений в ведомостях",

                "Время согласования ведомостей",

                "Процент ведомостей, принятых без доработок",

                "Количество задержек в отчетном периоде",

            ]

        return {

            "extracted": {

                "start_event": start_event,

                "end_event": end_event,

                "owner": owner,

                "perimeter": perimeter,

                "result_metrics": metrics,

            },

            "hints": hints,

            "examples": examples_norm,

            "metric_suggestions": metric_suggestions,

        }

    async def _get_step3_proposals(

        self,

        __request__,

        __user__: dict,

        raw_problem: str,

        problem_spec: dict,

        process_context: dict,

    ) -> Dict[str, Any]:

        system = (

            "Ты методолог A3/BPM в дорожно-строительной отрасли. "

            "На основе проблемы, конкретизации и контекста процесса предложи варианты названия ПРОЦЕССА и ПРОЕКТА улучшения. "

            "ВАЖНО:\n"

            "1) Название проекта — ТОЛЬКО существительным (например: 'Сокращение...', 'Устранение...', 'Оптимизация...', 'Снижение...', 'Повышение...', 'Стандартизация...'). "

            "НЕ начинай проект с глагола ('Сократить', 'Устранить', 'Оптимизировать' запрещено).\n"

            "2) Название процесса должно отражать поток работ по границам (start/end) и объект результата, "

            "а не управленческую функцию. Избегай шаблона 'Управление ...' — допускается максимум 1 раз среди 5 вариантов.\n"

            "3) Формулировки должны быть конкретными под контекст и границы.\n"

            "Верни СТРОГО JSON."

        )

        user_prompt = (

            "Сгенерируй:\n"

            "- 5 вариантов НАЗВАНИЯ ПРОЦЕССА (сквозного потока работ), где существует проблема.\n"

            "  Требование: процесс должен 'чувствовать' границы: от start_event до end_event (по смыслу).\n"

            "  Примеры формата: 'Подача и обработка ...', 'Подготовка, согласование и ...', 'Списание ... и закрытие ...', "

            "  'Оформление ... и проведение ...', 'Подготовка отчётности ...'.\n"

            "- 3 варианта НАЗВАНИЯ ПРОЕКТА (как инициативы улучшения) — ТОЛЬКО существительными.\n\n"

            "Формат ответа (строго JSON):\n"

            "{\n"

            '  "process_variants": ["...","...","...","...","..."],\n'

            '  "project_variants": ["...","...","..."]\n'

            "}\n\n"

            f"Сырая проблема: {raw_problem}\n"

            f"Конкретизация (шаг 2): {problem_spec}\n"

            f"Контекст процесса (границы/владелец/периметр/метрики): {process_context}\n"

        )

        try:
            data = await self._call_llm_json(
                __request__,
                __user__,
                [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_prompt},
                ],
            )
        except Exception:
            return self._fallback_step3_proposals(raw_problem, process_context)

        pv = data.get("process_variants") or []

        prj = data.get("project_variants") or []

        if isinstance(pv, list):

            pv = [str(x).strip() for x in pv if str(x).strip()]

        else:

            pv = []

        if isinstance(prj, list):

            prj = [str(x).strip() for x in prj if str(x).strip()]

        else:

            prj = []

        return {"process_variants": pv[:5], "project_variants": prj[:3]}

    async def _get_step4_metric_proposals(

        self,

        __request__,

        __user__: dict,

        raw_problem: str,

        problem_spec: dict,

        process_context: dict,

    ) -> Dict[str, Any]:

        system = (

            "Ты методолог A3/BPM в дорожно-строительной отрасли. "

            "Твоя задача — предложить измеримые показатели текущего состояния, "

            "которые отражают масштаб проблемы. Никаких решений и автоматизации. "

            "Верни СТРОГО JSON."

        )

        user_prompt = (

            "Предложи 5 метрик текущего состояния (current state metrics) на основе "

            "проблемы, конкретизации и контекста процесса. Метрики — без значений, "

            "но измеримые и относящиеся к As-Is.\n\n"

            "Формат ответа (строго JSON):\n"

            "{\n"

            '  "metric_suggestions": ["...","...","...","...","..."]\n'

            "}\n\n"

            f"Сырая проблема: {raw_problem}\n"

            f"Конкретизация (шаг 2): {problem_spec}\n"

            f"Контекст процесса (шаг 3): {process_context}\n"

        )

        data = await self._call_llm_json(

            __request__,

            __user__,

            [

                {"role": "system", "content": system},

                {"role": "user", "content": user_prompt},

            ],

        )

        metrics = data.get("metric_suggestions") or []

        if isinstance(metrics, list):

            metrics = [str(x).strip() for x in metrics if str(x).strip()]

        else:

            metrics = []

        return {"metric_suggestions": metrics[:5]}

    async def _get_step6_problem_proposals(

        self,

        __request__,

        __user__: dict,

        raw_problem: str,

        problem_spec: dict,

        process_context: dict,

        current_metrics: list,

        target_metrics: list,

    ) -> Dict[str, Any]:

        system = (

            "Ты методолог A3/BPM в дорожно-строительной отрасли. "

            "Сформулируй 4–5 экспертных проблем для анализа коренных причин. "

            "Проблемы должны быть наблюдаемыми и связанными с процессом и метриками. "

            "Верни СТРОГО JSON."

        )

        user_prompt = (

            "Сформулируй 4–5 экспертных проблем для анализа коренных причин на основе контекста.\n\n"

            "Формат ответа (строго JSON):\n"

            "{\n"

            '  "problems": ["...","...","...","..."]\n'

            "}\n\n"

            f"Сырая проблема: {raw_problem}\n"

            f"Конкретизация (шаг 2): {problem_spec}\n"

            f"Контекст процесса (шаг 3): {process_context}\n"

            f"Текущие метрики (шаг 4): {current_metrics}\n"

            f"Целевые метрики (шаг 5): {target_metrics}\n"

        )

        data = await self._call_llm_json(

            __request__,

            __user__,

            [

                {"role": "system", "content": system},

                {"role": "user", "content": user_prompt},

            ],

        )

        problems = data.get("problems") or []

        if isinstance(problems, list):

            problems = [str(x).strip() for x in problems if str(x).strip()]

        else:

            problems = []

        return {"problems": problems[:5]}

    async def _get_step6_why_suggestions(
        self,
        __request__,
        __user__: dict,
        effect: str,
    ) -> Dict[str, Any]:
        system = (
            "\u0422\u044b \u043c\u0435\u0442\u043e\u0434\u043e\u043b\u043e\u0433 A3/BPM. \u0421\u0444\u043e\u0440\u043c\u0443\u043b\u0438\u0440\u0443\u0439 3-5 \u043f\u0440\u0438\u0447\u0438\u043d (\u041d\u0415 \u0434\u0435\u0439\u0441\u0442\u0432\u0438\u0439), "
            "\u043f\u043e\u0447\u0435\u043c\u0443 \u043f\u0440\u043e\u0438\u0441\u0445\u043e\u0434\u0438\u0442 \u0443\u043a\u0430\u0437\u0430\u043d\u043d\u044b\u0439 \u044d\u0444\u0444\u0435\u043a\u0442. "
            "\u042d\u0442\u043e \u0434\u043e\u043b\u0436\u043d\u044b \u0431\u044b\u0442\u044c \u0438\u043c\u0435\u043d\u043d\u043e \u043f\u0440\u0438\u0447\u0438\u043d\u044b, \u0430 \u043d\u0435 \u0448\u0430\u0433\u0438 \u0438 \u043d\u0435 \u043a\u043e\u043d\u0442\u0440\u043c\u0435\u0440\u044b. "
            "\u041e\u0442\u0432\u0435\u0442 \u0434\u0430\u0439 \u043d\u0430 \u0440\u0443\u0441\u0441\u043a\u043e\u043c \u044f\u0437\u044b\u043a\u0435."
        )

        user_prompt = (
            "\u0414\u0430\u0439 3-5 \u0432\u0430\u0440\u0438\u0430\u043d\u0442\u043e\u0432 \u043e\u0442\u0432\u0435\u0442\u0430 \u043d\u0430 \u0432\u043e\u043f\u0440\u043e\u0441 \"\u041f\u043e\u0447\u0435\u043c\u0443?\". "
            "\u041a\u0430\u0436\u0434\u044b\u0439 \u0432\u0430\u0440\u0438\u0430\u043d\u0442 \u0441 \u043d\u043e\u0432\u043e\u0439 \u0441\u0442\u0440\u043e\u043a\u0438. \u0411\u0435\u0437 JSON.\n\n"
            f"\u0422\u0435\u043a\u0443\u0449\u0438\u0439 \u044d\u0444\u0444\u0435\u043a\u0442/\u043f\u0440\u043e\u0431\u043b\u0435\u043c\u0430: {effect}\n"
        )

        llm_raw = ""
        llm_err = ""
        try:
            content, _ = await self._chat_once_with_fallback(
                __request__,
                __user__,
                [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_prompt},
                ],
            )
            llm_raw = (content or "").strip().lstrip("\ufeff")
            if not llm_raw:
                llm_err = "empty_content"
        except Exception as e:
            llm_err = f"llm_error: {e}"
            llm_raw = ""

        suggestions: List[str] = []
        parsed = None
        if llm_raw:
            try:
                parsed = json.loads(llm_raw)
            except Exception:
                parsed = None

        if isinstance(parsed, list):
            suggestions = [str(x).strip() for x in parsed if str(x).strip()]
        elif isinstance(parsed, dict):
            for key in ("why_suggestions", "reasons", "causes", "answers", "items"):
                if key in parsed and isinstance(parsed[key], list):
                    suggestions = [str(x).strip() for x in parsed[key] if str(x).strip()]
                    break

        if not suggestions:
            suggestions = self._extract_llm_list(llm_raw)

        suggestions = self._normalize_list(suggestions, limit=5)
        if not suggestions:
            suggestions = self._step6_why_fallback(effect)
        return {
            "why_suggestions": suggestions[:5],
            "llm_raw": llm_raw,
            "llm_error": llm_err,
        }

    async def _get_step6_root_hint(
        self,
        __request__,
        __user__: dict,
        answer: str,
        active_problem: str = "",
        chain: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        # Compatibility helper for tests and backward integrations.
        # Runtime flow currently uses explicit command-based фиксацию.
        return {"is_root": False, "reason": ""}

    async def _get_step7_countermeasures(
        self,
        __request__,
        __user__: dict,
        root_cause: str,
        process_ctx: dict,
        problem_spec: dict,
        current_metrics: list,
        target_metrics: list,
    ) -> dict:
        system = (
            "\u0422\u044b \u2014 \u043c\u0435\u0442\u043e\u0434\u043e\u043b\u043e\u0433 A3/Lean. \u041f\u0440\u0435\u0434\u043b\u043e\u0436\u0438 3-5 \u043a\u043e\u043d\u043a\u0440\u0435\u0442\u043d\u044b\u0445 \u043a\u043e\u043d\u0442\u0440\u043c\u0435\u0440 "
            "\u0434\u043b\u044f \u0443\u0441\u0442\u0440\u0430\u043d\u0435\u043d\u0438\u044f \u043a\u043e\u0440\u043d\u0435\u0432\u043e\u0439 \u043f\u0440\u0438\u0447\u0438\u043d\u044b. \u041e\u0442\u0432\u0435\u0442 \u043d\u0430 \u0440\u0443\u0441\u0441\u043a\u043e\u043c \u044f\u0437\u044b\u043a\u0435."
        )
        user_prompt = (
            "\u041a\u043e\u0440\u043d\u0435\u0432\u0430\u044f \u043f\u0440\u0438\u0447\u0438\u043d\u0430:\n"
            f"{root_cause}\n\n"
            "\u041a\u043e\u043d\u0442\u0435\u043a\u0441\u0442 \u043f\u0440\u043e\u0446\u0435\u0441\u0441\u0430:\n"
            f"{json.dumps(process_ctx, ensure_ascii=False, indent=2)}\n\n"
            "\u041a\u043e\u043d\u043a\u0440\u0435\u0442\u0438\u0437\u0430\u0446\u0438\u044f \u043f\u0440\u043e\u0431\u043b\u0435\u043c\u044b:\n"
            f"{json.dumps(problem_spec, ensure_ascii=False, indent=2)}\n\n"
            "\u0422\u0435\u043a\u0443\u0449\u0438\u0435 \u043c\u0435\u0442\u0440\u0438\u043a\u0438:\n"
            f"{json.dumps(current_metrics, ensure_ascii=False, indent=2)}\n\n"
            "\u0426\u0435\u043b\u0435\u0432\u044b\u0435 \u043c\u0435\u0442\u0440\u0438\u043a\u0438:\n"
            f"{json.dumps(target_metrics, ensure_ascii=False, indent=2)}\n\n"
            "\u0412\u0435\u0440\u043d\u0438 3-5 \u043f\u0443\u043d\u043a\u0442\u043e\u0432, \u043a\u0430\u0436\u0434\u044b\u0439 \u0441 \u043d\u043e\u0432\u043e\u0439 \u0441\u0442\u0440\u043e\u043a\u0438. \u0411\u0435\u0437 JSON."
        )

        llm_raw = ""
        llm_err = ""
        try:
            content, _ = await self._chat_once_with_fallback(
                __request__,
                __user__,
                [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_prompt},
                ],
            )
            llm_raw = (content or "").strip().lstrip("\ufeff")
            if not llm_raw:
                llm_err = "empty_content"
        except Exception as e:
            llm_err = f"llm_error: {e}"
            llm_raw = ""

        actions: List[str] = []
        parsed = None
        if llm_raw:
            try:
                parsed = json.loads(llm_raw)
            except Exception:
                parsed = None

        if isinstance(parsed, list):
            actions = [str(x).strip() for x in parsed if str(x).strip()]
        elif isinstance(parsed, dict):
            for key in ("actions", "countermeasures", "items"):
                if key in parsed and isinstance(parsed[key], list):
                    actions = [str(x).strip() for x in parsed[key] if str(x).strip()]
                    break

        if not actions:
            actions = self._extract_llm_list(llm_raw)

        if not actions:
            actions = self._step7_countermeasure_fallback(root_cause)
            if not llm_err:
                llm_err = "fallback_only"

        actions = self._normalize_list(actions, limit=5)
        return {"actions": actions[:5], "llm_raw": llm_raw, "llm_error": llm_err}

    async def _get_step7_plan_from_actions(
        self,
        __request__,
        __user__: dict,
        actions: List[str],
        process_ctx: dict,
    ) -> dict:
        system = (
            "\u0422\u044b \u2014 \u043c\u0435\u0442\u043e\u0434\u043e\u043b\u043e\u0433 A3/Lean. \u041f\u0440\u0435\u0432\u0440\u0430\u0442\u0438 \u0434\u0435\u0439\u0441\u0442\u0432\u0438\u044f \u0432 \u043f\u043b\u0430\u043d \u043c\u0435\u0440\u043e\u043f\u0440\u0438\u044f\u0442\u0438\u0439. "
            "\u041d\u0443\u0436\u043d\u043e: \u043c\u0435\u0440\u043e\u043f\u0440\u0438\u044f\u0442\u0438\u0435, \u043e\u0436\u0438\u0434\u0430\u0435\u043c\u044b\u0439 \u0440\u0435\u0437\u0443\u043b\u044c\u0442\u0430\u0442, \u043e\u0442\u0432\u0435\u0442\u0441\u0442\u0432\u0435\u043d\u043d\u044b\u0439 (\u0440\u043e\u043b\u044c), \u0441\u0440\u043e\u043a."
        )
        user_prompt = (
            "\u0414\u0435\u0439\u0441\u0442\u0432\u0438\u044f:\n"
            + "\n".join([f"- {a}" for a in actions])
            + "\n\n\u041a\u043e\u043d\u0442\u0435\u043a\u0441\u0442 \u043f\u0440\u043e\u0446\u0435\u0441\u0441\u0430:\n"
            + f"{json.dumps(process_ctx, ensure_ascii=False, indent=2)}\n\n"
            + "\u0412\u0435\u0440\u043d\u0438 \u0421\u0422\u0420\u041e\u0413\u041e JSON \u0444\u043e\u0440\u043c\u0430\u0442\u0430:\n"
            + '{"plan":[{"action":"...","expected_result":"...","owner":"...","due":"..."}]}'
        )
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user_prompt},
        ]
        return await self._call_llm_json(__request__, __user__, messages)

    # ===================== MAIN =====================

    async def pipe(

        self,

        body: dict,

        __user__: dict,

        __request__,

        __event_emitter__=None,

        __task__=None,

        __metadata__=None,

    ):

        if __task__ is not None:

            return

        user_id = str(__user__["id"])

        user_text = self._extract_user_text(body).strip()

        cmd_line = self._first_cmd_line(user_text)
        if not cmd_line:
            m = _re_search(r"(\/(?:startnew|continue|projects|summary)\b.*)", user_text, flags=_re.IGNORECASE)
            if m:
                cmd_line = m.group(1).strip()
        cmd = cmd_line.lower().strip()
        cmd = cmd.strip("`")

        project_id = self._get_active_project(user_id)

        # -------- commands --------

        if cmd == "/projects":

            projects = self._list_projects()

            if not projects:

                return "📂 Пока нет проектов."

            return "📂 Проекты:\n" + "\n".join([f"- {p}" for p in projects])

        # ✅ /startnew: force-create fresh project

        if cmd.startswith("/startnew"):

            parts = cmd_line.split()

            if len(parts) < 2:

                return "❗Укажи ID проекта: `/startnew A3-0006`"

            new_id = parts[1].strip()

            if not new_id:

                return "❗Укажи ID проекта: `/startnew A3-0006`"

            self._set_active_project(user_id, new_id)

            project_id = new_id

            self._save_state(

                project_id,

                {"project_id": project_id, "current_step": 1, "meta": {}, "data": {}},

            )

            step1 = self._load_step(1)

            return (

                f"🆕 Создан новый проект: {project_id}\n\n"

                f"📌 Шаг 1: {step1.get('title','')}\n\n"

                f"{step1.get('instruction','')}\n\n"

                f"Команды: `/summary`, `/projects`, `/continue <ID>`, `/startnew <ID>`"

            )

        if cmd.startswith("/continue"):

            parts = cmd_line.split()

            if len(parts) < 2:

                return "❗Укажи ID проекта: `/continue X-001`"

            new_id = parts[1].strip()

            if not new_id:

                return "❗Укажи ID проекта: `/continue X-001`"

            self._set_active_project(user_id, new_id)

            project_id = new_id

            if not self._state_path(project_id).exists():

                self._save_state(

                    project_id,

                    {

                        "project_id": project_id,

                        "current_step": 1,

                        "meta": {},

                        "data": {},

                    },

                )

            step1 = self._load_step(1)

            return (

                f"🆕 Активный проект: {project_id}\n\n"

                f"📌 Шаг 1: {step1.get('title','')}\n\n"

                f"{step1.get('instruction','')}\n\n"

                f"Команды: `/summary`, `/projects`, `/continue <ID>`, `/startnew <ID>`"

            )

        # load state

        state = self._load_state(project_id)

        current_step = int(state.get("current_step", 1))

        # meta

        state.setdefault("meta", {})

        if "step3_phase" not in state["meta"]:

            state["meta"]["step3_phase"] = "context"

        if "step4_phase" not in state["meta"]:

            state["meta"]["step4_phase"] = "proposal"

        if "step6_phase" not in state["meta"]:
            state["meta"]["step6_phase"] = "select_problem"
        if "step7_phase" not in state["meta"]:
            state["meta"]["step7_phase"] = "countermeasures"

        if cmd == "/summary":

            raw_problem = state.get("data", {}).get("steps", {}).get("raw_problem", {})

            spec = state.get("data", {}).get("steps", {}).get("problem_spec", {})

            process_ctx = (

                state.get("data", {}).get("steps", {}).get("process_context", {})

            )

            process_def = (

                state.get("data", {}).get("steps", {}).get("process_definition", {})

            )

            step4_metrics = (

                state.get("data", {}).get("steps", {}).get("current_state_metrics", [])

            )

            step5_metrics = (

                state.get("data", {}).get("steps", {}).get("target_state_metrics", [])

            )

            step6_active = (

                state.get("data", {}).get("steps", {}).get("step6_active_problem", "")

            )

            step6_chain = (

                state.get("data", {}).get("steps", {}).get("step6_why_chain", [])

            )

            step6_roots = (
                state.get("data", {}).get("steps", {}).get("root_causes", [])
            )
            step7_plan = (
                state.get("data", {}).get("steps", {}).get("step7_plan", [])
            )

            lines = [

                f"📊 Проект: {project_id}",

                "",

                f"Текущий шаг: {current_step}",

                "",

                "Шаг 1 — Сырая проблема:",

            ]

            lines.append(

                f"- {raw_problem.get('raw_problem_sentence','')}"

                if raw_problem

                else "- ещё не задана"

            )

            lines += ["", "Шаг 2 — Конкретизация:"]

            if spec:

                lines.append(f"- Где/когда: {spec.get('where_when','')}")

                lines.append(f"- Масштаб: {spec.get('scale','')}")

                lines.append(f"- Последствия: {spec.get('consequences','')}")

                lines.append(f"- Кто страдает: {spec.get('who_suffers','')}")

                lines.append(f"- Деньги: {spec.get('money_impact','')}")

            else:

                lines.append("- ещё не заполнена")

            lines += ["", "Шаг 3 — Процесс (контекст):"]

            if process_ctx:

                lines.append(f"- Начало: {process_ctx.get('start_event','')}")

                lines.append(f"- Окончание: {process_ctx.get('end_event','')}")

                lines.append(f"- Владелец: {process_ctx.get('owner','')}")

                lines.append(f"- Периметр: {process_ctx.get('perimeter','')}")

                metrics = process_ctx.get("result_metrics") or []

                lines.append(

                    "- Метрики: " + "; ".join([str(m) for m in metrics])

                    if metrics

                    else "- Метрики: ещё не заданы"

                )

            else:

                lines.append("- ещё не заполнен")

            if process_def:

                lines += ["", "Шаг 3 — Выбор:"]

                lines.append(f"- Процесс: {process_def.get('process_name','')}")

                lines.append(f"- Проект: {process_def.get('project_title','')}")

            lines += ["", "Шаг 4 — Текущие метрики:"]

            if step4_metrics:

                for m in step4_metrics:

                    if isinstance(m, dict):

                        name = (m.get("metric") or "").strip()

                        val = (m.get("current_value") or "").strip()

                        if name and val:

                            lines.append(f"- {name}: {val}")

                        elif name:

                            lines.append(f"- {name}")

                    else:

                        name = str(m).strip()

                        if name:

                            lines.append(f"- {name}")

            else:

                lines.append("- ещё не заданы")

            lines += ["", "Шаг 5 — Целевые значения:"]

            if step5_metrics:

                for m in step5_metrics:

                    if isinstance(m, dict):

                        name = (m.get("metric") or "").strip()

                        val = (m.get("target_value") or "").strip()

                        if name and val:

                            lines.append(f"- {name}: {val}")

                        elif name:

                            lines.append(f"- {name}")

                    else:

                        name = str(m).strip()

                        if name:

                            lines.append(f"- {name}")

            else:

                lines.append("- ещё не заданы")

            lines += ["", "Шаг 6 — Анализ причин:"]

            if step6_active:

                lines.append(f"- Активная проблема: {step6_active}")

            if step6_chain:

                lines.append("- Цепочка почему (последние 3):")

                for w in step6_chain[-3:]:

                    level = w.get("level")

                    answer = w.get("answer")

                    lines.append(f"- Почему {level}: {answer}")

            chains_by_problem = (

                state.get("data", {}).get("steps", {}).get("step6_chains_by_problem", {})

            )

            if not isinstance(chains_by_problem, dict):

                chains_by_problem = {}

            if chains_by_problem:

                lines.append("- Цепочки почему:")

                for problem, chain in chains_by_problem.items():

                    lines.append(f"- Проблема: {problem}")

                    if isinstance(chain, list):

                        for w in chain:

                            level = w.get("level")

                            answer = w.get("answer")

                            lines.append(f"- Почему {level}: {answer}")

            if step6_roots:

                lines.append("- Корневые причины:")

                for r in step6_roots:

                    rc = r.get("root_cause")

                    pr = r.get("problem")

                    if pr:

                        lines.append(f"- {pr} -> {rc}")

                    else:

                        lines.append(f"- {rc}")

            if not step6_active and not step6_chain and not step6_roots and not chains_by_problem:

                lines.append("- нет данных")

            if not step6_active and not step6_chain and not step6_roots:
                lines.append("- ещё не задано")

            lines += ["", "Шаг 7 — План улучшений:"]
            if step7_plan:
                for p in step7_plan:
                    if isinstance(p, dict):
                        action = (p.get("action") or "").strip()
                        owner = (p.get("owner") or "").strip()
                        due = (p.get("due") or "").strip()
                        if action:
                            tail = []
                            if owner:
                                tail.append(f"ответственный: {owner}")
                            if due:
                                tail.append(f"срок: {due}")
                            suffix = f" ({', '.join(tail)})" if tail else ""
                            lines.append(f"- {action}{suffix}")
                    else:
                        action = str(p).strip()
                        if action:
                            lines.append(f"- {action}")
            else:
                lines.append("- ещё не задан")

            lines.append("")
            lines.append("Команды: `/summary`, `/projects`, `/continue <ID>`, `/startnew <ID>`")
            return "\n".join(lines)

        # show instruction if empty

        if not user_text and current_step not in (6,):
            try:

                step = self._load_step(current_step)

                return (

                    f"📌 Шаг {step.get('step_id', current_step)}: {step.get('title','')}\n\n"

                    f"{step.get('instruction','')}\n\n"

                    "✍️ Напиши ответ и отправь сообщение.\n\n"

                    "Команды: `/summary`, `/projects`, `/continue <ID>`, `/startnew <ID>`"

                )

            except Exception:

                return (

                    f"📌 Текущий шаг: {current_step}\n\n"

                    f"❗Не найден step_{current_step}.json в папке steps.\n\n"

                    "Команды: `/summary`, `/projects`, `/continue <ID>`, `/startnew <ID>`"

                )

        # audit raw

        state["data"].setdefault("raw", {})

        state["data"]["raw"][f"step_{current_step}"] = user_text

        self._save_state(project_id, state)

        # ================= STEP 1 =================

        if current_step == 1:

            if not self._looks_like_one_sentence(user_text):

                return (

                    "⚠️ На шаге 1 нужна одна простая фраза.\n\n"

                    "Напиши проблему одним предложением (симптом), без причин и без решений.\n"

                    "Пример: «Лимиты на использование машин и механизмов согласовываются несвоевременно».\n\n"

                    "Команды: `/summary`, `/projects`, `/continue <ID>`, `/startnew <ID>`"

                )

            if self._contains_solution_language(user_text):

                return (

                    "⚠️ На шаге 1 фиксируем только симптом, без решений.\n\n"

                    "Переформулируй одним предложением без слов «автоматизировать/оптимизировать/внедрить/улучшить…».\n"

                    "Пример: «…согласовывается несвоевременно / часто задерживается / не выполняется в срок».\n\n"

                    "Команды: `/summary`, `/projects`, `/continue <ID>`, `/startnew <ID>`"

                )

            state["data"].setdefault("steps", {})

            state["data"]["steps"]["raw_problem"] = {

                "raw_problem_sentence": user_text.strip()

            }

            state["current_step"] = 2

            self._save_state(project_id, state)

            raw_problem = user_text.strip()

            try:

                llm_data = await self._get_step2_hints_and_extract(

                    __request__, __user__, raw_problem, ""

                )

                hints = self._normalize_list(llm_data.get("hints") or [], limit=6)
                if not hints:
                    hints = self._default_step2_hints(raw_problem)

            except Exception:

                hints = []

            step2 = self._load_step(2)

            msg = (

                "✅ Шаг 1 готов.\n\n"

                f"➡️ Шаг 2: {step2.get('title','')}\n\n"

                f"{step2.get('instruction','')}\n\n"

                "Ответь одним сообщением по шаблону:\n"

                "```\nГде/когда: ...\nМасштаб: ...\nПоследствия: ...\nКто страдает: ...\nДеньги: ...\n```\n"

            )

            if hints:

                msg += "\nПодсказки (по твоей проблеме):\n" + "\n".join(

                    [f"- {h}" for h in hints]

                )

            msg += "\n\nКоманды: `/summary`, `/projects`, `/continue <ID>`, `/startnew <ID>`"

            return msg

        # ================= STEP 2 =================

        if current_step == 2:

            raw_problem = (

                state.get("data", {})

                .get("steps", {})

                .get("raw_problem", {})

                .get("raw_problem_sentence", "")

            )

            if self._is_update_variants_cmd(user_text):

                try:

                    data = await self._get_step2_hints_and_extract(

                        __request__, __user__, raw_problem, ""

                    )

                except Exception:

                    data = {"hints": [], "extracted": {}}

                hints = self._normalize_list(data.get("hints") or [], limit=6)
                if not hints:
                    hints = self._default_step2_hints(raw_problem)

                msg = (

                    "🔁 Варианты обновлены.\n\n"

                    "Ответь одним сообщением по шаблону:\n"

                    "```\nГде/когда: ...\nМасштаб: ...\nПоследствия: ...\nКто страдает: ...\nДеньги: ...\n```\n"

                )

                if hints:

                    msg += "\nПодсказки (по твоей проблеме):\n" + "\n".join(

                        [f"- {h}" for h in hints]

                    )

                msg += "\n\nКоманды: `/summary`, `/projects`, `/continue <ID>`, `/startnew <ID>`"

                return msg

            try:

                data = await self._get_step2_hints_and_extract(

                    __request__, __user__, raw_problem, user_text

                )

            except Exception as e:
                data = {
                    "extracted": self._extract_step2_fields_local(user_text),
                    "hints": self._default_step2_hints(raw_problem),
                    "llm_error": str(e),
                }

            extracted = data.get("extracted") or {}

            hints = self._normalize_list(data.get("hints") or [], limit=6)
            if not hints:
                hints = self._default_step2_hints(raw_problem)

            state["data"].setdefault("steps", {})

            state["data"]["steps"]["problem_spec"] = extracted

            self._save_state(project_id, state)

            filled_count, strong_count, _, _ = (

                self._count_filled_and_strong_fields_step2(extracted)

            )

            hints_block = ""

            if hints:

                hints_block = "\n\nПодсказки (по твоей проблеме):\n" + "\n".join(

                    [f"- {h}" for h in hints]

                )

            if filled_count < 4 or strong_count < 2:

                return (

                    "⚠️ Пока недостаточно конкретики, чтобы двигаться дальше.\n\n"

                    "Ответь одним сообщением по шаблону:\n"

                    "```\nГде/когда: ...\nМасштаб: ...\nПоследствия: ...\nКто страдает: ...\nДеньги: ...\n```\n"

                    + hints_block

                    + "\n\nКоманды: `/summary`, `/projects`, `/continue <ID>`, `/startnew <ID>`"

                )

            # move to step 3

            state["current_step"] = 3

            state["meta"]["step3_phase"] = "context"

            self._save_state(project_id, state)

            # ✅ Mini-fix #1: show rich Step 3 immediately (no extra user "ok")

            if self._step_exists(3):

                try:

                    step3_ctx = (

                        await self._get_step3_context_hints_examples_and_extract(

                            __request__,

                            __user__,

                            raw_problem=raw_problem,

                            problem_spec=extracted,

                            user_text_step3="",

                        )

                    )

                except Exception:

                    step3_ctx = {"hints": [], "examples": {}, "metric_suggestions": []}

                hints3 = step3_ctx.get("hints") or []

                examples3 = step3_ctx.get("examples") or {}

                metric_sug = step3_ctx.get("metric_suggestions") or []

                step3 = self._load_step(3)

                msg = (

                    "✅ Шаг 2 готов.\n\n"  # ✅ Mini-fix #2: no duplicated step2 hints on success

                    f"➡️ Шаг 3: {step3.get('title','')}\n\n"

                    f"{step3.get('instruction','')}\n\n"

                    "Ответь одним сообщением по шаблону:\n"

                    "```\nСобытие начала: ...\nСобытие окончания: ...\nВладелец процесса: ...\nПериметр: ...\nМетрики результата (2–4, без чисел): ...\n```\n"

                )

                if hints3:

                    msg += "\nПодсказки:\n" + "\n".join([f"- {h}" for h in hints3])

                ex_lines = []

                if examples3.get("start_event"):

                    ex_lines.append("  Примеры события начала (под твой кейс):")

                    ex_lines += [f"  - `{x}`" for x in examples3.get("start_event")[:2]]

                if examples3.get("end_event"):

                    ex_lines.append("  Примеры события окончания (под твой кейс):")

                    ex_lines += [f"  - `{x}`" for x in examples3.get("end_event")[:2]]

                if examples3.get("owner"):

                    ex_lines.append("  Примеры владельца процесса (роль/ответственный):")

                    ex_lines += [f"  - `{x}`" for x in examples3.get("owner")[:2]]

                if examples3.get("perimeter"):
                    ex_lines.append("  Примеры периметра (кто участвует):")
                    ex_lines += [f"  - `{x}`" for x in examples3.get("perimeter")[:5]]

                if ex_lines:

                    msg += "\n\n" + "\n".join(ex_lines)

                if metric_sug:

                    msg += "\n\n  Примеры метрик результата (предложение, выбери 2–4):\n"

                    msg += "\n".join([f"- `{m}`" for m in metric_sug[:5]])

                msg += "\n\nКоманды: `/summary`, `/projects`, `/continue <ID>`, `/startnew <ID>`"

                return msg

            return (

                "✅ Шаг 2 готов.\n\n"

                "➡️ Дальше должен быть Шаг 3, но файл `step_3.json` пока не найден.\n"

                "Создай `step_3.json` в папке steps — и продолжим.\n\n"

                "Команды: `/summary`, `/projects`, `/continue <ID>`, `/startnew <ID>`"

            )

        # ================= STEP 3 (context + proposal) =================

        if current_step == 3:

            raw_problem = (

                state.get("data", {})

                .get("steps", {})

                .get("raw_problem", {})

                .get("raw_problem_sentence", "")

            )

            problem_spec = (

                state.get("data", {}).get("steps", {}).get("problem_spec", {})

            )

            phase = (state.get("meta", {}) or {}).get("step3_phase") or "context"

            state["meta"]["step3_phase"] = phase

            # ---------- PHASE: proposal ----------

            if phase == "proposal":

                regen = (user_text or "").strip().lower() in {

                    "обнови варианты",

                    "обновить варианты",

                    "/regen",

                    "regen",

                    "r",

                }

                ctx = state.get("data", {}).get("steps", {}).get("process_context", {})

                if regen:

                    proposals = await self._get_step3_proposals(

                        __request__, __user__, raw_problem, problem_spec, ctx

                    )

                    state["data"].setdefault("steps", {})

                    state["data"]["steps"]["process_proposals"] = proposals

                    self._save_state(project_id, state)

                    pv = proposals.get("process_variants", [])

                    prj = proposals.get("project_variants", [])

                    msg = "🔁 Варианты обновлены.\n\n"

                    if pv:

                        msg += "Процессы (варианты):\n" + "\n".join(

                            [f"- `{x}`" for x in pv]

                        ) + "\n\n"

                    if prj:

                        msg += "Проекты (варианты):\n" + "\n".join(

                            [f"- `{x}`" for x in prj]

                        ) + "\n\n"

                    msg += "Ответь одним сообщением по шаблону:\n"

                    msg += "```\nПроцесс: ...\nНазвание проекта: ...\n```\n"

                    msg += "Команды: `/summary`, `/projects`, `/continue <ID>`, `/startnew <ID>`"

                    return msg

                proposals = (

                    state.get("data", {}).get("steps", {}).get("process_proposals", {})

                )

                if not proposals:

                    proposals = await self._get_step3_proposals(

                        __request__, __user__, raw_problem, problem_spec, ctx

                    )

                    state["data"].setdefault("steps", {})

                    state["data"]["steps"]["process_proposals"] = proposals

                    self._save_state(project_id, state)

                pv = proposals.get("process_variants", [])

                prj = proposals.get("project_variants", [])

                if (user_text or "").strip().isdigit():

                    msg = "⚠️ Не вижу выбор.\n\n"

                    if pv:

                        msg += "Процессы (варианты):\n" + "\n".join(

                            [f"- `{x}`" for x in pv]

                        ) + "\n\n"

                    if prj:

                        msg += "Проекты (варианты):\n" + "\n".join(

                            [f"- `{x}`" for x in prj]

                        ) + "\n\n"

                    msg += "Ответь одним сообщением по шаблону:\n"

                    msg += "```\nПроцесс: ...\nПроект: ...\n```\n"

                    msg += "Чтобы обновить варианты — напиши: `обнови варианты`.\n\n"

                    msg += "Команды: `/summary`, `/projects`, `/continue <ID>`, `/startnew <ID>`"

                    return msg

                if user_text and user_text.strip().isdigit():

                    msg = "⚠️ Не вижу выбор.\n\n"

                    if pv:

                        msg += "Процессы (варианты):\n" + "\n".join(

                            [f"- `{x}`" for x in pv]

                        ) + "\n\n"

                    if prj:

                        msg += "Проекты (варианты):\n" + "\n".join(

                            [f"- `{x}`" for x in prj]

                        ) + "\n\n"

                    msg += "Ответь одним сообщением по шаблону:\n"

                    msg += "```\nПроцесс: ...\nНазвание проекта: ...\n```\n"

                    msg += "Чтобы обновить варианты — напиши: `обнови варианты`.\n\n"

                    msg += "Команды: `/summary`, `/projects`, `/continue <ID>`, `/startnew <ID>`"

                    return msg

                # --- custom names (no regex) ---

                process_name = ""

                project_title = ""

                for ln in (user_text or "").splitlines():

                    line = ln.strip()

                    low = line.lower()

                    if low.startswith("\u043f\u0440\u043e\u0446\u0435\u0441\u0441:"):

                        process_name = line.split(":", 1)[1].strip()

                    if low.startswith("\u043d\u0430\u0437\u0432\u0430\u043d\u0438\u0435 \u043f\u0440\u043e\u0435\u043a\u0442\u0430:") or low.startswith("\u043f\u0440\u043e\u0435\u043a\u0442:"):

                        project_title = line.split(":", 1)[1].strip()

                if process_name and project_title:

                    if process_name and project_title:

                        state["data"].setdefault("steps", {})

                        state["data"]["steps"]["process_definition"] = {

                            "process_name": process_name,

                            "project_title": project_title,

                            "notes": "custom",

                        }

                        state["meta"]["step3_phase"] = "done"

                        state["current_step"] = 4

                        state["meta"]["step4_phase"] = "proposal"

                        self._save_state(project_id, state)

                        if self._step_exists(4):

                            try:

                                step4_data = await self._get_step4_metric_proposals(

                                    __request__,

                                    __user__,

                                    raw_problem,

                                    problem_spec,

                                    ctx,

                                )

                            except Exception:

                                step4_data = {"metric_suggestions": []}

                            step4 = self._load_step(4)

                            sugg = step4_data.get("metric_suggestions") or []

                            state["data"].setdefault("steps", {})

                            state["data"]["steps"][

                                "current_state_metric_proposals"

                            ] = step4_data

                            self._save_state(project_id, state)

                            msg = (

                                "✅ Шаг 3 завершён.\n\n"

                                f"Выбрали процесс: {process_name}\n"

                                f"Название проекта: {project_title}\n\n"

                                f"➡️ Шаг 4: {step4.get('title','')}\n\n"

                                f"{step4.get('instruction','')}\n\n"

                                "Ответь одним сообщением по шаблону:\n"

                                "```\nМетрики:\n- ...\n- ...\n```\n"

                            )

                            if sugg:

                                msg += "\nМетрики (варианты):\n" + "\n".join(

                                    [f"- `{x}`" for x in sugg]

                                )

                            msg += (

                                "\n\n"

                                "Значения запросим следующим сообщением.\n\n"

                                "Команды: `/summary`, `/projects`, `/continue <ID>`, `/startnew <ID>`"

                            )

                            return msg

                        return (

                            "✅ Шаг 3 завершён.\n\n"

                            f"Выбрали процесс: {process_name}\n"

                            f"Название проекта: {project_title}\n\n"

                            "➡️ Следующий шаг (4) ещё не настроен: нет файла `step_4.json`.\n"

                            "Создай `step_4.json`, и продолжим.\n\n"

                            "Команды: `/summary`, `/projects`, `/continue <ID>`, `/startnew <ID>`"

                        )

                # --- strict choose ---

                if not (m_proc and m_proj):

                    msg = "⚠️ Не вижу выбор.\n\n"

                    if pv:

                        msg += "Процессы (варианты):\n" + "\n".join(

                            [f"- `{x}`" for x in pv]

                        ) + "\n\n"

                    if prj:

                        msg += "Проекты (варианты):\n" + "\n".join(

                            [f"- `{x}`" for x in prj]

                        ) + "\n\n"

                    msg += "Ответь одним сообщением по шаблону:\n"

                    msg += "```\nПроцесс: ...\nНазвание проекта: ...\n```\n"

                    msg += "Чтобы обновить варианты — напиши: `обнови варианты`.\n\n"

                    msg += "Команды: `/summary`, `/projects`, `/continue <ID>`, `/startnew <ID>`"

                    return msg

                process_name = m_proc.group(1).strip()

                project_title = m_proj.group(1).strip()

                if not process_name or not project_title:

                    return (

                        "⚠️ Не вижу выбор. Используй шаблон.\n\n"

                        "Команды: `/summary`, `/projects`, `/continue <ID>`, `/startnew <ID>`"

                    )

                state["data"].setdefault("steps", {})

                state["data"]["steps"]["process_definition"] = {

                    "process_name": process_name,

                    "project_title": project_title,

                    "notes": "",

                }

                state["meta"]["step3_phase"] = "done"

                state["current_step"] = 4

                state["meta"]["step4_phase"] = "proposal"

                self._save_state(project_id, state)

                if self._step_exists(4):

                    try:

                        step4_data = await self._get_step4_metric_proposals(

                            __request__,

                            __user__,

                            raw_problem,

                            problem_spec,

                            ctx,

                        )

                    except Exception:

                        step4_data = {"metric_suggestions": []}

                    step4 = self._load_step(4)

                    sugg = step4_data.get("metric_suggestions") or []

                    state["data"].setdefault("steps", {})

                    state["data"]["steps"][

                        "current_state_metric_proposals"

                    ] = step4_data

                    self._save_state(project_id, state)

                    msg = (

                        "✅ Шаг 3 завершён.\n\n"

                        f"Выбрали процесс: {process_name}\n"

                        f"Название проекта: {project_title}\n\n"

                        f"➡️ Шаг 4: {step4.get('title','')}\n\n"

                        f"{step4.get('instruction','')}\n\n"

                        "Ответь одним сообщением по шаблону:\n"

                        "```\nМетрики:\n- ...\n- ...\n```\n"

                    )

                    if sugg:

                        msg += "\nМетрики (варианты):\n" + "\n".join(

                            [f"- `{x}`" for x in sugg]

                        )

                    msg += (

                        "\n\n"

                        "Значения запросим следующим сообщением.\n\n"

                        "Команды: `/summary`, `/projects`, `/continue <ID>`, `/startnew <ID>`"

                    )

                    return msg

                return (

                    "✅ Шаг 3 завершён.\n\n"

                    f"Выбрали процесс: {process_name}\n"

                    f"Название проекта: {project_title}\n\n"

                    "➡️ Следующий шаг (4) ещё не настроен: нет файла `step_4.json`.\n"

                    "Создай `step_4.json`, и продолжим.\n\n"

                    "Команды: `/summary`, `/projects`, `/continue <ID>`, `/startnew <ID>`"

                )

            # ---------- PHASE: context ----------
            regen = self._is_update_variants_cmd(user_text)
            ctx_data = await self._get_step3_context_hints_examples_and_extract(
                __request__, __user__, raw_problem, problem_spec, "" if regen else user_text
            )

            extracted = ctx_data.get("extracted") or {}

            hints = ctx_data.get("hints") or []

            examples = ctx_data.get("examples") or {}

            metric_suggestions = ctx_data.get("metric_suggestions") or []

            state["data"].setdefault("steps", {})

            existing_ctx = (

                state.get("data", {}).get("steps", {}).get("process_context", {}) or {}

            )

            looks_template = self._looks_like_step3_template(user_text)

            if user_text and not looks_template:

                # Don't trust LLM extraction if user didn't follow the template.

                merged = {

                    "start_event": (existing_ctx.get("start_event") or "").strip(),

                    "end_event": (existing_ctx.get("end_event") or "").strip(),

                    "owner": (existing_ctx.get("owner") or "").strip(),

                    "perimeter": (existing_ctx.get("perimeter") or "").strip(),

                    "result_metrics": existing_ctx.get("result_metrics") or [],

                }

                extracted = merged

            else:

                merged = {

                    "start_event": (existing_ctx.get("start_event") or "").strip(),

                    "end_event": (existing_ctx.get("end_event") or "").strip(),

                    "owner": (existing_ctx.get("owner") or "").strip(),

                    "perimeter": (existing_ctx.get("perimeter") or "").strip(),

                    "result_metrics": existing_ctx.get("result_metrics") or [],

                }

                if (extracted.get("start_event") or "").strip():

                    merged["start_event"] = extracted.get("start_event").strip()

                if (extracted.get("end_event") or "").strip():

                    merged["end_event"] = extracted.get("end_event").strip()

                if (extracted.get("owner") or "").strip():

                    merged["owner"] = extracted.get("owner").strip()

                if (extracted.get("perimeter") or "").strip():

                    merged["perimeter"] = extracted.get("perimeter").strip()

                metrics = extracted.get("result_metrics") or []

                if isinstance(metrics, list):

                    metrics = [str(x).strip() for x in metrics if str(x).strip()]

                else:

                    metrics = []

                if metrics:

                    merged["result_metrics"] = metrics

                extracted = merged

            state["data"]["steps"]["process_context"] = extracted

            self._save_state(project_id, state)

            ready, missing = self._step3_context_ready(extracted)

            # ✅ если контекст заполнен — сразу переходим к вариантам

            if ready:

                proposals = await self._get_step3_proposals(

                    __request__, __user__, raw_problem, problem_spec, extracted

                )

                state["data"].setdefault("steps", {})

                state["data"]["steps"]["process_proposals"] = proposals

                state["meta"]["step3_phase"] = "proposal"

                self._save_state(project_id, state)

                pv = proposals.get("process_variants", [])

                prj = proposals.get("project_variants", [])

                out = "✅ Контекст процесса зафиксирован.\n\n"

                out += "Теперь выбери, как назвать процесс и проект (можно выбрать или написать своё).\n\n"

                if pv:

                    out += "Процессы (варианты):\n" + "\n".join(

                        [f"- `{x}`" for x in pv]

                    ) + "\n\n"

                if prj:

                    out += "Проекты (варианты):\n" + "\n".join(

                        [f"- `{x}`" for x in prj]

                    ) + "\n\n"

                out += "Ответь одним сообщением по шаблону:\n"

                out += "```\nПроцесс: ...\nНазвание проекта: ...\n```\n"

                out += "Чтобы обновить варианты — напиши: `обнови варианты`.\n\n"

                out += "Команды: `/summary`, `/projects`, `/continue <ID>`, `/startnew <ID>`"

                return out

            step3 = self._load_step(3) if self._step_exists(3) else {}

            missing_map = {

                "start_event": "Событие начала",

                "end_event": "Событие окончания",

                "owner": "Владелец процесса",

                "perimeter": "Периметр",

                "result_metrics (>=2)": "Метрики результата (минимум 2)",

            }

            missing_human = [missing_map.get(m, m) for m in missing]

            missing_block = ""

            if missing_human:

                missing_block = (

                    "⚠️ Пока не хватает:\n"

                    + "\n".join([f"- {m}" for m in missing_human])

                    + "\n\n"

                )

            msg = (
                f"🧩 Шаг 3: {step3.get('title','Процесс')}\n\n"
                f"{step3.get('instruction','')}\n\n"
                + missing_block
                + "Ответь одним сообщением по шаблону:\n"
                "```\nСобытие начала: ...\n"
                "Событие окончания: ...\n"
                "Владелец процесса: ...\n"
                "Периметр: ...\n"
                "Метрики результата (2–4, без чисел): ...\n```\n"
            )

            if hints:

                msg += "\nПодсказки:\n" + "\n".join([f"- {h}" for h in hints])

            ex_lines = []

            if examples.get("start_event"):

                ex_lines.append("Примеры события начала (под твой кейс):")

                ex_lines += [f"- `{x}`" for x in examples.get("start_event")[:2]]

            if examples.get("end_event"):

                ex_lines.append("Примеры события окончания (под твой кейс):")

                ex_lines += [f"- `{x}`" for x in examples.get("end_event")[:2]]

            if examples.get("owner"):

                ex_lines.append("Примеры владельца процесса (роль/ответственный):")

                ex_lines += [f"- `{x}`" for x in examples.get("owner")[:2]]

            if examples.get("perimeter"):
                ex_lines.append("Примеры периметра (кто участвует):")
                ex_lines += [f"- `{x}`" for x in examples.get("perimeter")[:5]]

            if ex_lines:

                msg += "\n\n" + "\n".join(ex_lines)

            if metric_suggestions:
                msg += "\n\nПримеры метрик результата (предложение, выбери 2–4):\n"
                msg += "\n".join([f"- `{m}`" for m in metric_suggestions[:5]])

            msg += "\n\nЧтобы обновить варианты — напиши: `обнови варианты`."
            msg += "\n\nКоманды: `/summary`, `/projects`, `/continue <ID>`, `/startnew <ID>`"
            return msg

        # ================= STEP 4 =================

        if current_step == 4:

            raw_problem = (

                state.get("data", {})

                .get("steps", {})

                .get("raw_problem", {})

                .get("raw_problem_sentence", "")

            )

            problem_spec = (

                state.get("data", {}).get("steps", {}).get("problem_spec", {})

            )

            process_ctx = (

                state.get("data", {}).get("steps", {}).get("process_context", {})

            )

            phase = (state.get("meta", {}) or {}).get("step4_phase") or "proposal"

            state["meta"]["step4_phase"] = phase

            regen = (user_text or "").strip().lower() in {

                "обнови варианты",

                "обновить варианты",

                "/regen",

                "regen",

                "r",

            }

            if phase == "values":

                metrics = (

                    state.get("data", {})

                    .get("steps", {})

                    .get("current_state_metrics", [])

                )

                if not metrics:

                    state["meta"]["step4_phase"] = "proposal"

                    self._save_state(project_id, state)

                    return (

                        "⚠️ Не нашёл выбранные метрики. Давай выберем их заново.\n"

                        "Напиши: `обнови варианты`.\n\n"

                        "Команды: `/summary`, `/projects`, `/continue <ID>`, `/startnew <ID>`"

                    )

                metrics = self._parse_metric_values(user_text, metrics, "current_value")

                missing = [

                    m.get("metric")

                    for m in metrics

                    if not (m.get("current_value") or "").strip()

                ]

                if missing:

                    msg = (

                        "⚠️ Нужны текущие значения для всех выбранных метрик.\n\n"

                        "Ответь одним сообщением по шаблону:\n"

                        "```\n"

                    )

                    msg += "\n\n".join(

                        [

                            f"Метрика: {m.get('metric')}\nТекущее значение: ..."

                            for m in metrics

                        ]

                    )

                    msg += "\n```\n\nКоманды: `/summary`, `/projects`, `/continue <ID>`, `/startnew <ID>`"

                    state["data"].setdefault("steps", {})

                    state["data"]["steps"]["current_state_metrics"] = metrics

                    self._save_state(project_id, state)

                    return msg

                state["data"].setdefault("steps", {})

                state["data"]["steps"]["current_state_metrics"] = metrics

                state["meta"]["step4_phase"] = "done"

                state["current_step"] = 5

                self._save_state(project_id, state)

                # show step 5 prompt immediately

                # show step 5 template immediately

                tmpl = "\n\n".join(

                    [

                        f"Метрика: {m.get('metric')}\nЦелевое значение: ..."

                        for m in metrics

                    ]

                )

                return (

                    "✅ Шаг 4 завершён.\n\n"

                    "Зафиксированы метрики текущего состояния.\n\n"

                    "🧩 Шаг 5: Целевое состояние: показатели, которых хотим добиться\n\n"

                    "Укажите целевые (желаемые) значения по каждой метрике процесса.\n"

                    "Это нужно, чтобы зафиксировать каким должен стать процесс после внедрения улучшений (основа для расчёта разрыва и плана действий).\n"

                    "Заполните значения после «Целевое значение».\n\n"

                    "Ответь одним сообщением по шаблону:\n"

                    "```\n"

                    f"{tmpl}\n"

                    "```\n\n"

                    "Команды: `/summary`, `/projects`, `/continue <ID>`, `/startnew <ID>`"

                )

            if phase == "proposal":

                if regen:

                    try:

                        proposals = await self._get_step4_metric_proposals(

                            __request__, __user__, raw_problem, problem_spec, process_ctx

                        )

                    except Exception as e:

                        return (

                            "⚠️ Не смог обновить варианты метрик.\n"

                            "Попробуй ещё раз или напиши свои метрики в формате:\n"

                            "Метрика: ...\n\n"

                            "Значения запросим следующим сообщением.\n\n"

                            "Команды: `/summary`, `/projects`, `/continue <ID>`, `/startnew <ID>`"

                        )

                    state["data"].setdefault("steps", {})

                    state["data"]["steps"][

                        "current_state_metric_proposals"

                    ] = proposals

                    self._save_state(project_id, state)

                    sugg = proposals.get("metric_suggestions", [])

                    if not sugg:

                        return (

                            "⚠️ Не удалось получить варианты метрик.\n"

                            "Попробуй ещё раз или напиши свои метрики :\n"

                            "Метрика: ...\n\n"

                            "Команды: `/summary`, `/projects`, `/continue <ID>`, `/startnew <ID>`"

                        )

                    msg = "🔁 Варианты обновлены.\n\n"

                    if sugg:

                        msg += "Метрики (варианты):\n" + "\n".join(

                            [f"- `{x}`" for x in sugg]

                        )

                        msg += "\n\n"

                    msg += (

                        "Ответь одним сообщением по шаблону:\n"

                        "```\nМетрики:\n- ...\n- ...\n```\n\n"

                        "Значения запросим следующим сообщением.\n\n"

                        "Чтобы обновить метрики — напиши: `обнови варианты`.\n\n"

                        "Команды: `/summary`, `/projects`, `/continue <ID>`, `/startnew <ID>`"

                    )

                    return msg

                selected = self._parse_metrics_template(user_text)

                custom = self._extract_custom_metrics(user_text)

                if selected:

                    metrics = self._dedupe_metrics(

                        [{"metric": s, "current_value": ""} for s in selected]

                    )

                elif custom:

                    metrics = self._dedupe_metrics(custom)

                else:

                    proposals = (

                        state.get("data", {})

                        .get("steps", {})

                        .get("current_state_metric_proposals", {})

                    )

                    if not proposals:

                        try:

                            proposals = await self._get_step4_metric_proposals(

                                __request__,

                                __user__,

                                raw_problem,

                                problem_spec,

                                process_ctx,

                            )

                        except Exception as e:

                            return (

                                "⚠️ Не смог получить варианты метрик.\n"

                                "Попробуй ещё раз или напиши свои метрики по шаблону:\n"

                                "```\nМетрики:\n- ...\n- ...\n```\n\n"

                                "Значения запросим следующим сообщением.\n\n"

                                "Команды: `/summary`, `/projects`, `/continue <ID>`, `/startnew <ID>`"

                            )

                        state["data"].setdefault("steps", {})

                        state["data"]["steps"][

                            "current_state_metric_proposals"

                        ] = proposals

                        self._save_state(project_id, state)

                    sugg = proposals.get("metric_suggestions") or []

                    if not sugg:

                        return (

                            "⚠️ Нет доступных вариантов метрик.\n"

                            "Напиши свои метрики по шаблону:\n"

                            "```\nМетрики:\n- ...\n- ...\n```\n\n"

                            "Команды: `/summary`, `/projects`, `/continue <ID>`, `/startnew <ID>`"

                        )

                    msg = (
                        "🧩 Шаг 4: Текущее состояние: показатели проблемы\n\n"
                        "На этом шаге фиксируем показатели процесса, по которым видно, что проблема существует.\n"
                        "Ответь одним сообщением по шаблону:\n"
                        "```\nМетрики:\n- ...\n- ...\n```\n\n"
                        "**Справка по сбору данных (кратко)**\n"
                        "_Зачем:_ понять, откуда берутся цифры по выбранным метрикам и можно ли их подтвердить.\n\n"
                        "- Проверяемость: можно ли измерить и проверить каждый показатель.\n"
                        "- Источник: 1С/учётная система/журналы/наряды/хронометраж/фото‑видео.\n"
                        "- Период: неделя/месяц/квартал.\n"
                        "- Где в процессе проблема выражена сильнее всего.\n"
                        "- Виды потерь (Muda): ожидание, переделка, транспортировка, лишняя обработка и т.п.\n\n"
                        "_Важно:_ выбирая показатели, помни — данные нужно подтверждать свидетельствами. Далее мы попросим текущие значения по выбранным метрикам.\n\n"
                        "Метрики (варианты):\n"
                        + "\n".join([f"- `{x}`" for x in sugg])
                        + "\n\nЗначения запросим следующим сообщением.\n\n"
                        "Чтобы обновить метрики — напиши: `обнови варианты`.\n\n"
                        "Команды: `/summary`, `/projects`, `/continue <ID>`, `/startnew <ID>`"
                    )
                    return msg

                if not metrics:

                    step4 = self._load_step(4) if self._step_exists(4) else {}

                    msg = (
                        f"🧩 Шаг 4: {step4.get('title','')}\n\n"
                        f"{step4.get('instruction','')}\n\n"
                        "Ответь одним сообщением по шаблону:\n"
                        "```\nМетрики:\n- ...\n- ...\n```\n\n"
                    )
                    if sugg:
                        msg += "\nМетрики (варианты):\n" + "\n".join(
                            [f"- `{x}`" for x in sugg]
                        )
                    msg += (
                        "\n\n**Справка по сбору данных (кратко)**\n"
                        "_Зачем:_ понять, откуда берутся цифры по выбранным метрикам и можно ли их подтвердить.\n\n"
                        "- Проверяемость: можно ли измерить и проверить каждый показатель.\n"
                        "- Источник: 1С/учётная система/журналы/наряды/хронометраж/фото‑видео.\n"
                        "- Период: неделя/месяц/квартал.\n"
                        "- Где в процессе проблема выражена сильнее всего.\n"
                        "- Виды потерь (Muda): ожидание, переделка, транспортировка, лишняя обработка и т.п.\n\n"
                        "_Важно:_ выбирая показатели, помни — данные нужно подтверждать свидетельствами. Далее мы попросим текущие значения по выбранным метрикам.\n\n"
                        "Значения запросим следующим сообщением.\n\n"
                        "Чтобы обновить метрики — напиши: `обнови варианты`.\n\n"
                        "Команды: `/summary`, `/projects`, `/continue <ID>`, `/startnew <ID>`"
                    )
                    return msg

                if len(metrics) < 2:

                    return (

                        "⚠️ Нужно минимум 2 метрики текущего состояния.\n"

                        "Ответь одним сообщением по шаблону:\n"

                        "```\nМетрики:\n- ...\n- ...\n```\n\n"

                        "Команды: `/summary`, `/projects`, `/continue <ID>`, `/startnew <ID>`"

                    )

                if len(metrics) > 5:

                    return (

                        "⚠️ Нужны 2–5 метрик. Сейчас их больше 5.\n"

                        "Сократи список и отправь снова.\n\n"

                        "Команды: `/summary`, `/projects`, `/continue <ID>`, `/startnew <ID>`"

                    )

                state["data"].setdefault("steps", {})

                state["data"]["steps"]["current_state_metrics"] = metrics

                state["meta"]["step4_phase"] = "values"

                self._save_state(project_id, state)

                msg = "Ответь одним сообщением по шаблону:\n"

                msg += "```\n"

                msg += "\n\n".join(

                    [

                        f"Метрика: {m.get('metric')}\nТекущее значение: ..."

                        for m in metrics

                    ]

                )

                msg += "\n```\n\nКоманды: `/summary`, `/projects`, `/continue <ID>`, `/startnew <ID>`"

                return msg

        # ================= STEP 5 =================

        if current_step == 5:

            current_metrics = (

                state.get("data", {})

                .get("steps", {})

                .get("current_state_metrics", [])

            )

            if not current_metrics:

                return (

                    "⚠️ Не найдены метрики шага 4. Сначала выбери метрики текущего состояния.\n\n"

                    "Команды: `/summary`, `/projects`, `/continue <ID>`, `/startnew <ID>`"

                )

            target_metrics = [

                {"metric": m.get("metric"), "target_value": ""}

                for m in current_metrics

                if isinstance(m, dict) and (m.get("metric") or "").strip()

            ]

            if not target_metrics:

                return (

                    "⚠️ Не удалось сформировать список метрик для целевых значений.\n\n"

                    "Команды: `/summary`, `/projects`, `/continue <ID>`, `/startnew <ID>`"

                )

            def _step5_prompt(metrics_list: List[Dict[str, str]]) -> str:

                msg = (

                    "🧩 Шаг 5: Целевое состояние: показатели, которых хотим добиться\n\n"

                    "Укажите целевые (желаемые) значения по каждой метрике процесса.\n"

                    "Это нужно, чтобы зафиксировать каким должен стать процесс после внедрения улучшений (основа для расчёта разрыва и плана действий).\n"

                    "Заполните значения после «Целевое значение».\n\n"

                    "Ответь одним сообщением по шаблону:\n"

                    "```\n"

                )

                msg += (

                    "\n\n".join(

                        [

                            f"Метрика: {m.get('metric')}\nЦелевое значение: ..."

                            for m in metrics_list

                        ]

                    )

                    + "\n"

                )

                msg += "```\n"

                msg += "\n\nКоманды: `/summary`, `/projects`, `/continue <ID>`, `/startnew <ID>`"

                return msg

            if not (user_text or "").strip():

                return _step5_prompt(target_metrics)

            try:

                target_metrics = self._parse_metric_values(

                    user_text, target_metrics, "target_value"

                )

            except Exception:

                return _step5_prompt(target_metrics)

            missing = [

                m.get("metric")

                for m in target_metrics

                if not (m.get("target_value") or "").strip()

            ]

            if missing:

                return _step5_prompt(target_metrics)

            state["data"].setdefault("steps", {})

            state["data"]["steps"]["target_state_metrics"] = target_metrics

            state["current_step"] = 6

            self._save_state(project_id, state)

            # transition to step 6

            state["meta"]["step6_phase"] = "select_problem"

            self._save_state(project_id, state)

            raw_problem = (

                state.get("data", {})

                .get("steps", {})

                .get("raw_problem", {})

                .get("raw_problem_sentence", "")

            )

            problem_spec = (

                state.get("data", {}).get("steps", {}).get("problem_spec", {})

            )

            process_ctx = (

                state.get("data", {}).get("steps", {}).get("process_context", {})

            )

            current_metrics = (

                state.get("data", {}).get("steps", {}).get("current_state_metrics", [])

            )

            target_metrics = (

                state.get("data", {}).get("steps", {}).get("target_state_metrics", [])

            )

            try:

                p_data = await self._get_step6_problem_proposals(

                    __request__,

                    __user__,

                    raw_problem,

                    problem_spec,

                    process_ctx,

                    current_metrics,

                    target_metrics,

                )

            except Exception:

                p_data = {"problems": []}

            problems = p_data.get("problems") or []

            pool = []

            if raw_problem:

                pool.append(f"{raw_problem} (✅ изначальная проблема)")

            pool += problems

            pool = [p for p in pool if str(p).strip()][:6]

            state["data"].setdefault("steps", {})

            state["data"]["steps"]["step6_problem_pool"] = pool

            state["data"]["steps"]["step6_pending_problems"] = []

            state["data"]["steps"]["step6_active_problem"] = ""

            state["data"]["steps"]["step6_why_chain"] = []

            self._save_state(project_id, state)

            msg = (

                "✅ Шаг 5 завершён.\n\n"

                "Зафиксированы целевые значения метрик.\n\n"

                "🧩 Шаг 6: Анализ коренных причин (5 Почему)\n\n"

                "Выбери проблему для анализа (одну за раз) или напиши свою.\n\n"

            )

            if pool:
                msg += "Проблемы (варианты):\n" + "\n".join([f"- `{x}`" for x in pool]) + "\n\n"
            msg += (
                "Ответь одним сообщением по шаблону:\n"
                "```\nПроблемы:\n- ...\n- ...\n```\n\n"
                "Чтобы обновить варианты — напиши: `обнови варианты`.\n\n"
                "Команды: `/summary`, `/projects`, `/continue <ID>`, `/startnew <ID>`"
            )
            return msg

        # ================= STEP 6 =================
        if current_step == 6:
            raw_problem = (

                state.get("data", {})

                .get("steps", {})

                .get("raw_problem", {})

                .get("raw_problem_sentence", "")

            )

            problem_spec = (

                state.get("data", {}).get("steps", {}).get("problem_spec", {})

            )

            process_ctx = (

                state.get("data", {}).get("steps", {}).get("process_context", {})

            )

            current_metrics = (

                state.get("data", {}).get("steps", {}).get("current_state_metrics", [])

            )

            target_metrics = (

                state.get("data", {}).get("steps", {}).get("target_state_metrics", [])

            )

            phase = (state.get("meta", {}) or {}).get("step6_phase") or "select_problem"

            state["meta"]["step6_phase"] = phase

            def _normalize_list(items, limit=10):

                if not isinstance(items, list):

                    return []

                out = []

                for x in items:

                    s = str(x).strip()

                    if s:

                        out.append(s)

                return out[:limit]

            def _parse_problems_template(text_in: str):
                def _clean_line(s: str) -> str:
                    return (
                        (s or "")
                        .replace("\ufeff", "")
                        .replace("\u200b", "")
                        .replace("\u200c", "")
                        .replace("\u200d", "")
                        .strip()
                    )

                lines = [_clean_line(ln) for ln in (text_in or "").splitlines()]
                lines = [ln for ln in lines if ln]
                if not lines:
                    return []
                head = lines[0].lower()
                if not (head.startswith("проблемы:") or head.startswith("проблемы")):
                    return []
                items = []
                tail = ""
                if ":" in head:
                    tail = head.split(":", 1)[1].strip()
                if tail:
                    items.append(tail)
                for ln in lines[1:]:
                    ln = ln.lstrip("-?*").strip()
                    if ln:
                        items.append(ln)

                items = [i for i in items if i and i.lower() != "проблемы:"]
                return _normalize_list(items, limit=10)

            def _looks_like_problem_list(text_in: str) -> bool:
                t = (
                    (text_in or "")
                    .replace("\ufeff", "")
                    .replace("\u200b", "")
                    .replace("\u200c", "")
                    .replace("\u200d", "")
                    .strip()
                )
                if not t:
                    return False
                low = t.lower()
                if "проблем" not in low:
                    return False
                if "\n-" in t or "\n•" in t:
                    return True
                if low.startswith("проблемы") and ":" in low:
                    return True
                return False

            def _step6_select_prompt(pool, updated=False):
                header = "\U0001F9E9 " + "\u0428\u0430\u0433 6: \u0410\u043d\u0430\u043b\u0438\u0437 \u043a\u043e\u0440\u0435\u043d\u043d\u044b\u0445 \u043f\u0440\u0438\u0447\u0438\u043d (5 \u041f\u043e\u0447\u0435\u043c\u0443)" + "\n\n"

                intro = "\u0412\u044b\u0431\u0435\u0440\u0438 \u043f\u0440\u043e\u0431\u043b\u0435\u043c\u044b \u0434\u043b\u044f \u0430\u043d\u0430\u043b\u0438\u0437\u0430 (\u043c\u043e\u0436\u043d\u043e \u043d\u0435\u0441\u043a\u043e\u043b\u044c\u043a\u043e) \u0438\u043b\u0438 \u043d\u0430\u043f\u0438\u0448\u0438 \u0441\u0432\u043e\u044e.\n\n"

                msg = ""

                if updated:

                    msg += "\U0001F501 " + "\u0412\u0430\u0440\u0438\u0430\u043d\u0442\u044b \u043e\u0431\u043d\u043e\u0432\u043b\u0435\u043d\u044b." + "\n\n"

                msg += header + intro

                if pool:

                    msg += "\u041f\u0440\u043e\u0431\u043b\u0435\u043c\u044b (\u0432\u0430\u0440\u0438\u0430\u043d\u0442\u044b):\n" + "\n".join([f"- `{x}`" for x in pool]) + "\n\n"

                msg += (

                    "\u041e\u0442\u0432\u0435\u0442\u044c \u043e\u0434\u043d\u0438\u043c \u0441\u043e\u043e\u0431\u0449\u0435\u043d\u0438\u0435\u043c \u043f\u043e \u0448\u0430\u0431\u043b\u043e\u043d\u0443:\n"

                    "```\n\u041f\u0440\u043e\u0431\u043b\u0435\u043c\u044b:\n- ...\n- ...\n```\n\n"

                    "\u0427\u0442\u043e\u0431\u044b \u043e\u0431\u043d\u043e\u0432\u0438\u0442\u044c \u0432\u0430\u0440\u0438\u0430\u043d\u0442\u044b \u2014 \u043d\u0430\u043f\u0438\u0448\u0438: `\u043e\u0431\u043d\u043e\u0432\u0438 \u0432\u0430\u0440\u0438\u0430\u043d\u0442\u044b`.\n\n"

                    "\u041a\u043e\u043c\u0430\u043d\u0434\u044b: `/summary`, `/projects`, `/continue <ID>`, `/startnew <ID>`"

                )

                return msg

            def _chain_block(chain):
                if not chain:
                    return ""
                lines = []
                for i, c in enumerate(chain):
                    ans = (c.get("answer", "") or "").strip()
                    if not ans:
                        continue
                    if _looks_like_problem_list(ans):
                        continue
                    lines.append(f"*\u041f\u043e\u0447\u0435\u043c\u0443 {i+1}: {ans}*")
                return "\n".join(lines) + "\n\n"

            def _step6_why_prompt(problem, suggestions, chain, updated=False, prefix_msg=""):

                msg = prefix_msg or ""

                if updated:

                    msg += "\U0001F501 " + "\u0412\u0430\u0440\u0438\u0430\u043d\u0442\u044b \u043e\u0431\u043d\u043e\u0432\u043b\u0435\u043d\u044b." + "\n\n"

                msg += "\U0001F9E9 " + "\u0428\u0430\u0433 6: 5 \u041f\u043e\u0447\u0435\u043c\u0443" + "\n\n"

                msg += f"\u041f\u0440\u043e\u0431\u043b\u0435\u043c\u0430: {problem}\n\n"

                chain_to_show = chain

                if chain and chain[0].get("answer", "").strip() == (problem or "").strip():

                    chain_to_show = chain[1:]

                msg += _chain_block(chain_to_show)

                msg += "\u041f\u043e\u0447\u0435\u043c\u0443?\n\n"

                # Hard guard: never show empty "Почему?" prompt without options.
                if not suggestions:
                    suggestions = self._step6_why_fallback(problem)

                if suggestions:

                    msg += "".join(["```\n" + x + "\n```\n\n" for x in suggestions])

                msg += (

                    "\u0421\u043a\u043e\u043f\u0438\u0440\u0443\u0439 \u043e\u0434\u0438\u043d \u0438\u0437 \u0432\u0430\u0440\u0438\u0430\u043d\u0442\u043e\u0432 \u0438\u043b\u0438 \u043d\u0430\u043f\u0438\u0448\u0438 \u0441\u0432\u043e\u0439 \u043e\u0442\u0432\u0435\u0442.\n"

                    "\u0427\u0442\u043e\u0431\u044b \u043e\u0431\u043d\u043e\u0432\u0438\u0442\u044c \u0432\u0430\u0440\u0438\u0430\u043d\u0442\u044b \u2014 \u043d\u0430\u043f\u0438\u0448\u0438: `\u043e\u0431\u043d\u043e\u0432\u0438 \u0432\u0430\u0440\u0438\u0430\u043d\u0442\u044b`.\n"

                    "\u0414\u043b\u044f \u0444\u0438\u043a\u0441\u0430\u0446\u0438\u0438 \u043a\u043e\u0440\u043d\u0435\u0432\u043e\u0439 \u043f\u0440\u0438\u0447\u0438\u043d\u044b \u043d\u0430\u043f\u0438\u0448\u0438: `\u0437\u0430\u0444\u0438\u043a\u0441\u0438\u0440\u043e\u0432\u0430\u0442\u044c \u043a\u0430\u043a \u043a\u043e\u0440\u043d\u0435\u0432\u0443\u044e`.\n"

                    "\u041a\u043e\u043c\u0430\u043d\u0434\u044b: `/summary`, `/projects`, `/continue <ID>`, `/startnew <ID>`"

                )

                return msg

            # ----- phase: select_problem -----

            if phase == "select_problem":

                if self._is_update_variants_cmd(user_text) or not state.get("data", {}).get("steps", {}).get(

                    "step6_problem_pool"

                ):

                    try:

                        p_data = await self._get_step6_problem_proposals(

                            __request__,

                            __user__,

                            raw_problem,

                            problem_spec,

                            process_ctx,

                            current_metrics,

                            target_metrics,

                        )

                    except Exception:

                        p_data = {"problems": []}

                    problems = _normalize_list(p_data.get("problems") or [], limit=6)

                    pool = []

                    if raw_problem:

                        raw_clean = self._clean_problem_text(raw_problem)

                        if raw_clean:

                            pool.append(f"{raw_clean} (\u2705 \u0438\u0437\u043d\u0430\u0447\u0430\u043b\u044c\u043d\u0430\u044f \u043f\u0440\u043e\u0431\u043b\u0435\u043c\u0430)")

                    pool += problems

                    pool = _normalize_list(pool, limit=6)

                    state["data"].setdefault("steps", {})

                    state["data"]["steps"]["step6_problem_pool"] = pool

                    self._save_state(project_id, state)

                else:

                    pool = _normalize_list(

                        state.get("data", {})

                        .get("steps", {})

                        .get("step6_problem_pool", [])

                    )

                if self._is_update_variants_cmd(user_text):

                    return _step6_select_prompt(pool, updated=True)

                selected = _parse_problems_template(user_text)
                if not selected:
                    custom_problem = self._extract_custom_problem(user_text)
                    if custom_problem:
                        selected = [custom_problem]
                    else:
                        return _step6_select_prompt(pool, updated=False)

                state["data"].setdefault("steps", {})

                state["data"]["steps"]["step6_selected_problems"] = selected

                state["data"]["steps"]["step6_pending_problems"] = selected[1:]

                state["data"]["steps"]["step6_active_problem"] = selected[0]

                state["data"]["steps"]["step6_why_chain"] = []

                state["data"]["steps"]["step6_chains_by_problem"] = {}

                state["data"]["steps"]["root_causes"] = state["data"]["steps"].get("root_causes", [])

                state["meta"]["step6_phase"] = "why_loop"

                self._save_state(project_id, state)

                prefix = "\u2705 \u041f\u0440\u043e\u0431\u043b\u0435\u043c\u044b \u0437\u0430\u0444\u0438\u043a\u0441\u0438\u0440\u043e\u0432\u0430\u043d\u044b. \u041d\u0430\u0447\u043d\u0435\u043c \u0441 \u043f\u0435\u0440\u0432\u043e\u0439.\n\n"
                try:
                    s_data = await self._get_step6_why_suggestions(
                        __request__, __user__, selected[0]
                    )
                except Exception:
                    s_data = {"why_suggestions": []}
                suggestions = _normalize_list(s_data.get("why_suggestions") or [], limit=5)
                state["data"]["steps"]["step6_why_suggestions"] = suggestions
                self._save_state(project_id, state)
                return _step6_why_prompt(
                    selected[0],
                    suggestions,
                    [],
                    prefix_msg=prefix,
                )

            # ----- phase: why_loop -----

            if phase == "why_loop":
                active_problem = (
                    state.get("data", {})
                    .get("steps", {})
                    .get("step6_active_problem", "")
                )
                chain = (
                    state.get("data", {})
                    .get("steps", {})
                    .get("step6_why_chain", [])
                )
                if isinstance(chain, list) and chain:
                    cleaned = [c for c in chain if not _looks_like_problem_list(c.get("answer", ""))]
                    if len(cleaned) != len(chain):
                        chain = cleaned
                        state["data"].setdefault("steps", {})
                        state["data"]["steps"]["step6_why_chain"] = chain
                        state["data"]["steps"].setdefault("step6_chains_by_problem", {})
                        if active_problem:
                            state["data"]["steps"]["step6_chains_by_problem"][active_problem] = chain
                        self._save_state(project_id, state)

                if not (active_problem or "").strip():

                    pool = _normalize_list(

                        state.get("data", {})

                        .get("steps", {})

                        .get("step6_problem_pool", [])

                    )

                    active_problem = raw_problem or (pool[0] if pool else "")

                    state["data"].setdefault("steps", {})

                    state["data"]["steps"]["step6_active_problem"] = active_problem

                    self._save_state(project_id, state)

                t = (user_text or "").strip().lower()

                if "\u0437\u0430\u0444\u0438\u043a\u0441" in t:

                    if not chain:

                        return "\u26A0\uFE0F \u0421\u043d\u0430\u0447\u0430\u043b\u0430 \u043d\u0443\u0436\u043d\u043e \u0432\u044b\u0431\u0440\u0430\u0442\u044c \u0445\u043e\u0442\u044f \u0431\u044b \u043e\u0434\u0438\u043d \u043e\u0442\u0432\u0435\u0442."

                    last = chain[-1]

                    roots = state.get("data", {}).get("steps", {}).get("root_causes", [])

                    count_for_problem = len([r for r in roots if r.get("problem") == active_problem])

                    if count_for_problem >= 3:

                        return "\u26A0\uFE0F \u041c\u0430\u043a\u0441\u0438\u043c\u0443\u043c 3 \u043a\u043e\u0440\u043d\u0435\u0432\u044b\u0435 \u043f\u0440\u0438\u0447\u0438\u043d\u044b \u043d\u0430 \u043e\u0434\u043d\u0443 \u043f\u0440\u043e\u0431\u043b\u0435\u043c\u0443."

                    roots.append(

                        {

                            "problem": active_problem,

                            "root_cause": last.get("answer"),

                            "type": "",

                            "process_point": "",

                            "controllable": "",

                            "change_hint": "",

                            "linked_chain_level": last.get("level"),

                        }

                    )

                    state["data"].setdefault("steps", {})

                    state["data"]["steps"]["root_causes"] = roots

                    self._save_state(project_id, state)

                    pending = (

                        state.get("data", {})

                        .get("steps", {})

                        .get("step6_pending_problems", [])

                    )

                    if pending:

                        next_problem = pending.pop(0)

                        state["data"]["steps"]["step6_active_problem"] = next_problem

                        state["data"]["steps"]["step6_pending_problems"] = pending

                        state["data"]["steps"]["step6_why_chain"] = []

                        self._save_state(project_id, state)

                        return _step6_why_prompt(

                            next_problem,

                            _normalize_list(state.get("data", {}).get("steps", {}).get("step6_why_suggestions", []), limit=5),

                            [],

                            prefix_msg="\u2705 \u041a\u043e\u0440\u043d\u0435\u0432\u0430\u044f \u043f\u0440\u0438\u0447\u0438\u043d\u0430 \u0437\u0430\u0444\u0438\u043a\u0441\u0438\u0440\u043e\u0432\u0430\u043d\u0430. \u041f\u0435\u0440\u0435\u0445\u043e\u0434\u0438\u043c \u043a \u0441\u043b\u0435\u0434\u0443\u044e\u0449\u0435\u0439 \u043f\u0440\u043e\u0431\u043b\u0435\u043c\u0435.\n\n",

                        )

                    state["meta"]["step6_phase"] = "done"
                    state["current_step"] = 7
                    self._save_state(project_id, state)
                    if self._step_exists(7):
                        process_ctx = (
                            state.get("data", {}).get("steps", {}).get("process_context", {})
                        )
                        problem_spec = (
                            state.get("data", {}).get("steps", {}).get("problem_spec", {})
                        )
                        current_metrics = (
                            state.get("data", {}).get("steps", {}).get("current_state_metrics", [])
                        )
                        target_metrics = (
                            state.get("data", {}).get("steps", {}).get("target_state_metrics", [])
                        )
                        roots_all = state.get("data", {}).get("steps", {}).get("root_causes", [])
                        root_texts = []
                        for rc in roots_all:
                            if isinstance(rc, dict):
                                txt = (rc.get("root_cause") or "").strip()
                            else:
                                txt = str(rc).strip()
                            if txt:
                                root_texts.append(txt)
                        if not root_texts:
                            return (
                                "\u2705 \u0428\u0430\u0433 6 \u0437\u0430\u0432\u0435\u0440\u0448\u0451\u043d.\n\n"
                                "\u0417\u0430\u0444\u0438\u043a\u0441\u0438\u0440\u043e\u0432\u0430\u043d\u044b \u043a\u043e\u0440\u043d\u0435\u0432\u044b\u0435 \u043f\u0440\u0438\u0447\u0438\u043d\u044b.\n\n"
                                "\u27a1\ufe0f \u0428\u0430\u0433 7: \u041a\u043e\u043d\u0442\u0440\u043c\u0435\u0440\u044b \u043f\u043e \u043a\u043e\u0440\u043d\u0435\u0432\u044b\u043c \u043f\u0440\u0438\u0447\u0438\u043d\u0430\u043c.\n\n"
                                "\u041e\u0442\u0432\u0435\u0442\u044c \u043e\u0434\u043d\u0438\u043c \u0441\u043e\u043e\u0431\u0449\u0435\u043d\u0438\u0435\u043c \u043f\u043e \u0448\u0430\u0431\u043b\u043e\u043d\u0443:\n"
                                "```\n\u041a\u043e\u043d\u0442\u0440\u043c\u0435\u0440\u044b:\n- ...\n- ...\n```\n\n"
                                "\u041a\u043e\u043c\u0430\u043d\u0434\u044b: `/summary`, `/projects`, `/continue <ID>`, `/startnew <ID>`"
                            )
                        active_root = root_texts[0]
                        pending_roots = root_texts[1:]
                        suggestions = []
                        llm_raw = ""
                        llm_error = ""
                        try:
                            s_data = await self._get_step7_countermeasures(
                                __request__,
                                __user__,
                                active_root,
                                process_ctx,
                                problem_spec,
                                current_metrics,
                                target_metrics,
                            )
                            suggestions = self._normalize_list(s_data.get("actions") or [], limit=5)
                            llm_raw = s_data.get("llm_raw", "")
                            llm_error = s_data.get("llm_error", "")
                        except Exception as e:
                            llm_error = f"handler_error: {e}"
                            suggestions = []

                        state["data"].setdefault("steps", {})
                        state["data"]["steps"]["step7_pending_root_causes"] = pending_roots
                        state["data"]["steps"]["step7_active_root_cause"] = active_root
                        state["data"]["steps"]["step7_suggestions_by_root"] = {active_root: suggestions}
                        state["data"]["steps"]["step7_llm_raw"] = llm_raw
                        state["data"]["steps"]["step7_llm_error"] = llm_error
                        self._save_state(project_id, state)

                        msg = (
                            "\u2705 \u0428\u0430\u0433 6 \u0437\u0430\u0432\u0435\u0440\u0448\u0451\u043d.\n\n"
                            "\u0417\u0430\u0444\u0438\u043a\u0441\u0438\u0440\u043e\u0432\u0430\u043d\u044b \u043a\u043e\u0440\u043d\u0435\u0432\u044b\u0435 \u043f\u0440\u0438\u0447\u0438\u043d\u044b.\n\n"
                            "\U0001f9e9 \u0428\u0430\u0433 7: \u041a\u043e\u043d\u0442\u0440\u043c\u0435\u0440\u044b \u043f\u043e \u043a\u043e\u0440\u043d\u0435\u0432\u044b\u043c \u043f\u0440\u0438\u0447\u0438\u043d\u0430\u043c\n\n"
                            f"\u041a\u043e\u0440\u043d\u0435\u0432\u0430\u044f \u043f\u0440\u0438\u0447\u0438\u043d\u0430: {active_root}\n\n"
                        )
                        if suggestions:
                            msg += "\u041a\u043e\u043d\u0442\u0440\u043c\u0435\u0440\u044b (\u0432\u0430\u0440\u0438\u0430\u043d\u0442\u044b):\n" + "\n".join(
                                [f"- `{x}`" for x in suggestions]
                            ) + "\n\n"
                        msg += (
                            "\u041e\u0442\u0432\u0435\u0442\u044c \u043e\u0434\u043d\u0438\u043c \u0441\u043e\u043e\u0431\u0449\u0435\u043d\u0438\u0435\u043c \u043f\u043e \u0448\u0430\u0431\u043b\u043e\u043d\u0443:\n"
                            "```\n\u041a\u043e\u043d\u0442\u0440\u043c\u0435\u0440\u044b:\n- ...\n- ...\n```\n\n"
                            "\u0427\u0442\u043e\u0431\u044b \u043e\u0431\u043d\u043e\u0432\u0438\u0442\u044c \u0432\u0430\u0440\u0438\u0430\u043d\u0442\u044b, \u043d\u0430\u043f\u0438\u0448\u0438: `\u043e\u0431\u043d\u043e\u0432\u0438 \u0432\u0430\u0440\u0438\u0430\u043d\u0442\u044b`.\n\n"
                            "\u041a\u043e\u043c\u0430\u043d\u0434\u044b: `/summary`, `/projects`, `/continue <ID>`, `/startnew <ID>`"
                        )
                        return msg
                    return (
                        "\u2705 \u0428\u0430\u0433 6 \u0437\u0430\u0432\u0435\u0440\u0448\u0451\u043d.\n\n"
                        "\u0417\u0430\u0444\u0438\u043a\u0441\u0438\u0440\u043e\u0432\u0430\u043d\u044b \u043a\u043e\u0440\u043d\u0435\u0432\u044b\u0435 \u043f\u0440\u0438\u0447\u0438\u043d\u044b.\n\n"
                        "\u27a1\ufe0f \u0421\u043b\u0435\u0434\u0443\u044e\u0449\u0438\u0439 \u0448\u0430\u0433 (7) \u0435\u0449\u0451 \u043d\u0435 \u043d\u0430\u0441\u0442\u0440\u043e\u0435\u043d: \u043d\u0435\u0442 \u0444\u0430\u0439\u043b\u0430 `step_7.json`.\n"
                        "\u0421\u043e\u0437\u0434\u0430\u0439 `step_7.json`, \u0438 \u043f\u0440\u043e\u0434\u043e\u043b\u0436\u0438\u043c.\n\n"
                        "\u041a\u043e\u043c\u0430\u043d\u0434\u044b: `/summary`, `/projects`, `/continue <ID>`, `/startnew <ID>`"
                    )

                regen = self._is_update_variants_cmd(user_text)

                if regen or not state.get("data", {}).get("steps", {}).get("step6_why_suggestions"):

                    try:

                        s_data = await self._get_step6_why_suggestions(

                            __request__, __user__, active_problem

                        )

                    except Exception:

                        s_data = {"why_suggestions": []}

                    state["data"].setdefault("steps", {})

                    state["data"]["steps"]["step6_why_suggestions"] = (

                        _normalize_list(s_data.get("why_suggestions") or [], limit=5)

                    )

                    self._save_state(project_id, state)

                suggestions = _normalize_list(

                    state.get("data", {})

                    .get("steps", {})

                    .get("step6_why_suggestions", [])

                    , limit=5

                )

                if not (user_text or "").strip() or regen:
                    return _step6_why_prompt(
                        active_problem,
                        suggestions,
                        chain,
                        updated=regen,
                        prefix_msg=prefix if "prefix" in locals() else "",
                    )

                if _parse_problems_template(user_text):
                    return _step6_why_prompt(
                        active_problem,
                        suggestions,
                        chain,
                    )
                if _looks_like_problem_list(user_text):
                    return _step6_why_prompt(
                        active_problem,
                        suggestions,
                        chain,
                    )

                answer = (user_text or "").strip()
                if not answer:
                    return _step6_why_prompt(
                        active_problem,
                        suggestions,
                        chain,
                    )
                if _looks_like_problem_list(answer):
                    return _step6_why_prompt(
                        active_problem,
                        suggestions,
                        chain,
                    )

                chain.append(

                    {

                        "level": len(chain) + 1,

                        "effect": active_problem,

                        "question": "\u041f\u043e\u0447\u0435\u043c\u0443?",

                        "answer": answer,

                        "classification": "",

                        "controllable": "",

                        "eliminates_problem": "",

                        "evidence": "",

                    }

                )

                state["data"]["steps"]["step6_why_chain"] = chain

                state["data"]["steps"].setdefault("step6_chains_by_problem", {})

                state["data"]["steps"]["step6_chains_by_problem"][active_problem] = chain

                self._save_state(project_id, state)

                try:

                    s_data = await self._get_step6_why_suggestions(

                        __request__, __user__, answer

                    )

                except Exception:

                    s_data = {"why_suggestions": []}

                suggestions = _normalize_list(s_data.get("why_suggestions") or [], limit=5)

                state["data"].setdefault("steps", {})

                state["data"]["steps"]["step6_why_suggestions"] = suggestions

                self._save_state(project_id, state)

                return _step6_why_prompt(
                    active_problem,
                    suggestions,
                    chain,
                )

        # ================= STEP 7 =================
        if current_step == 7:
            process_ctx = (
                state.get("data", {}).get("steps", {}).get("process_context", {})
            )
            problem_spec = (
                state.get("data", {}).get("steps", {}).get("problem_spec", {})
            )
            current_metrics = (
                state.get("data", {}).get("steps", {}).get("current_state_metrics", [])
            )
            target_metrics = (
                state.get("data", {}).get("steps", {}).get("target_state_metrics", [])
            )
            root_causes = (
                state.get("data", {}).get("steps", {}).get("root_causes", [])
            )

            phase = (state.get("meta", {}) or {}).get("step7_phase") or "countermeasures"
            state["meta"]["step7_phase"] = phase

            if not root_causes:
                return (
                    "⚠️ Сначала нужно зафиксировать корневые причины на шаге 6.\n\n"
                    "Команды: `/summary`, `/projects`, `/continue <ID>`, `/startnew <ID>`"
                )

            def _rc_text(rc):
                if isinstance(rc, dict):
                    return (rc.get("root_cause") or "").strip()
                return str(rc).strip()

            def _counter_prompt(root_text, actions, updated=False, prefix_msg=""):
                msg = prefix_msg or ""
                if updated:
                    msg += "\U0001f501 \u0412\u0430\u0440\u0438\u0430\u043d\u0442\u044b \u043e\u0431\u043d\u043e\u0432\u043b\u0435\u043d\u044b.\n\n"
                msg += "\U0001f9e9 \u0428\u0430\u0433 7: \u041a\u043e\u043d\u0442\u0440\u043c\u0435\u0440\u044b \u043f\u043e \u043a\u043e\u0440\u043d\u0435\u0432\u044b\u043c \u043f\u0440\u0438\u0447\u0438\u043d\u0430\u043c\n\n"
                msg += f"\u041a\u043e\u0440\u043d\u0435\u0432\u0430\u044f \u043f\u0440\u0438\u0447\u0438\u043d\u0430: {root_text}\n\n"
                if actions:
                    msg += "\u041a\u043e\u043d\u0442\u0440\u043c\u0435\u0440\u044b (\u0432\u0430\u0440\u0438\u0430\u043d\u0442\u044b):\n" + "\n".join([f"- `{x}`" for x in actions]) + "\n\n"
                msg += (
                    "\u041e\u0442\u0432\u0435\u0442\u044c \u043e\u0434\u043d\u0438\u043c \u0441\u043e\u043e\u0431\u0449\u0435\u043d\u0438\u0435\u043c \u043f\u043e \u0448\u0430\u0431\u043b\u043e\u043d\u0443:\n"
                    "```\n\u041a\u043e\u043d\u0442\u0440\u043c\u0435\u0440\u044b:\n- ...\n- ...\n```\n\n"
                    "\u0427\u0442\u043e\u0431\u044b \u043e\u0431\u043d\u043e\u0432\u0438\u0442\u044c \u0432\u0430\u0440\u0438\u0430\u043d\u0442\u044b, \u043d\u0430\u043f\u0438\u0448\u0438: `\u043e\u0431\u043d\u043e\u0432\u0438 \u0432\u0430\u0440\u0438\u0430\u043d\u0442\u044b`.\n\n"
                    "\u041a\u043e\u043c\u0430\u043d\u0434\u044b: `/summary`, `/projects`, `/continue <ID>`, `/startnew <ID>`"
                )
                return msg

            def _plan_prompt(plan_items, prefix_msg="", warnings=""):
                msg = prefix_msg or ""
                msg += "\U0001f9e9 \u0428\u0430\u0433 7: \u041f\u043b\u0430\u043d \u0443\u043b\u0443\u0447\u0448\u0435\u043d\u0438\u0439\n\n"
                msg += "\u041f\u0440\u043e\u0432\u0435\u0440\u044c \u0438 \u043f\u0440\u0438 \u043d\u0435\u043e\u0431\u0445\u043e\u0434\u0438\u043c\u043e\u0441\u0442\u0438 \u043e\u0442\u0440\u0435\u0434\u0430\u043a\u0442\u0438\u0440\u0443\u0439 \u043f\u043b\u0430\u043d. \u041e\u0442\u0432\u0435\u0442\u044c \u043f\u043e \u0448\u0430\u0431\u043b\u043e\u043d\u0443.\n\n"
                if warnings:
                    msg += warnings + "\n\n"
                if plan_items:
                    msg += "```\n"
                    msg += "\n\n".join(
                        [
                            "\u041c\u0435\u0440\u043e\u043f\u0440\u0438\u044f\u0442\u0438\u0435: {action}\n\u041e\u0436\u0438\u0434\u0430\u0435\u043c\u044b\u0439 \u0440\u0435\u0437\u0443\u043b\u044c\u0442\u0430\u0442: {expected}\n\u041e\u0442\u0432\u0435\u0442\u0441\u0442\u0432\u0435\u043d\u043d\u044b\u0439: {owner}\n\u0421\u0440\u043e\u043a: {due}".format(
                                action=p.get("action", ""),
                                expected=p.get("expected_result", ""),
                                owner=p.get("owner", ""),
                                due=p.get("due", ""),
                            )
                            for p in plan_items
                        ]
                    )
                    msg += "\n```\n\n"
                else:
                    msg += (
                        "```\n\u041c\u0435\u0440\u043e\u043f\u0440\u0438\u044f\u0442\u0438\u0435: ...\n\u041e\u0436\u0438\u0434\u0430\u0435\u043c\u044b\u0439 \u0440\u0435\u0437\u0443\u043b\u044c\u0442\u0430\u0442: ...\n\u041e\u0442\u0432\u0435\u0442\u0441\u0442\u0432\u0435\u043d\u043d\u044b\u0439: ...\n\u0421\u0440\u043e\u043a: ...\n```\n\n"
                    )
                msg += (
                    "\u0415\u0441\u043b\u0438 \u0432\u0441\u0451 \u043e\u043a, \u043d\u0430\u043f\u0438\u0448\u0438: `\u043e\u043a`.\n\n"
                    "\u041a\u043e\u043c\u0430\u043d\u0434\u044b: `/summary`, `/projects`, `/continue <ID>`, `/startnew <ID>`"
                )
                return msg
            # phase: countermeasures
            if phase == "countermeasures":
                root_texts = [t for t in (_rc_text(r) for r in root_causes) if t]
                if not root_texts:
                    return (
                        "⚠️ Не вижу корневых причин. Заполни шаг 6.\n\n"
                        "Команды: `/summary`, `/projects`, `/continue <ID>`, `/startnew <ID>`"
                    )

                steps = state.get("data", {}).get("steps", {})
                pending = steps.get("step7_pending_root_causes")
                active = (steps.get("step7_active_root_cause") or "").strip()
                if not isinstance(pending, list):
                    pending = root_texts[:]
                if not active:
                    active = pending.pop(0)
                state["data"].setdefault("steps", {})
                state["data"]["steps"]["step7_pending_root_causes"] = pending
                state["data"]["steps"]["step7_active_root_cause"] = active
                self._save_state(project_id, state)

                regen = self._is_update_variants_cmd(user_text)
                suggestions_by_root = steps.get("step7_suggestions_by_root", {})
                if not isinstance(suggestions_by_root, dict):
                    suggestions_by_root = {}

                if regen or not suggestions_by_root.get(active):
                    try:
                        s_data = await self._get_step7_countermeasures(
                            __request__,
                            __user__,
                            active,
                            process_ctx,
                            problem_spec,
                            current_metrics,
                            target_metrics,
                        )
                    except Exception as e:
                        s_data = {
                            "actions": [],
                            "llm_raw": "",
                            "llm_error": f"handler_error: {e}",
                        }
                    suggestions = self._normalize_list(s_data.get("actions") or [], limit=5)
                    suggestions_by_root[active] = suggestions
                    state["data"]["steps"]["step7_llm_raw"] = s_data.get("llm_raw", "")
                    state["data"]["steps"]["step7_llm_error"] = s_data.get("llm_error", "")
                    state["data"]["steps"]["step7_suggestions_by_root"] = suggestions_by_root
                    self._save_state(project_id, state)
                else:
                    suggestions = self._normalize_list(suggestions_by_root.get(active) or [], limit=5)

                if not (user_text or "").strip() or regen:
                    if not suggestions:
                        return (
                            "\u26a0\ufe0f \u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u043f\u043e\u043b\u0443\u0447\u0438\u0442\u044c \u0432\u0430\u0440\u0438\u0430\u043d\u0442\u044b \u043a\u043e\u043d\u0442\u0440\u043c\u0435\u0440 \u043e\u0442 LLM. "
                            "\u041f\u0440\u043e\u0432\u0435\u0440\u044c \u043c\u043e\u0434\u0435\u043b\u044c \u043c\u0435\u0442\u043e\u0434\u043e\u043b\u043e\u0433\u0430 \u0438\u043b\u0438 \u043f\u043e\u043f\u0440\u043e\u0431\u0443\u0439 \u0441\u043d\u043e\u0432\u0430: `\u043e\u0431\u043d\u043e\u0432\u0438 \u0432\u0430\u0440\u0438\u0430\u043d\u0442\u044b`.\n\n"
                            + _counter_prompt(active, suggestions, updated=regen)
                        )
                    return _counter_prompt(active, suggestions, updated=regen)

                selected = self._parse_actions_template(user_text)
                if not selected:
                    return _counter_prompt(active, suggestions, updated=False)

                selected = self._normalize_list(selected, limit=5)
                step7_counter = steps.get("step7_countermeasures", [])
                if not isinstance(step7_counter, list):
                    step7_counter = []
                step7_counter.append({"root_cause": active, "actions": selected})

                step7_selected = steps.get("step7_selected_actions", [])
                if not isinstance(step7_selected, list):
                    step7_selected = []
                step7_selected += selected
                step7_selected = self._normalize_list(step7_selected, limit=15)

                state["data"]["steps"]["step7_countermeasures"] = step7_counter
                state["data"]["steps"]["step7_selected_actions"] = step7_selected

                if pending:
                    next_root = pending.pop(0)
                    state["data"]["steps"]["step7_pending_root_causes"] = pending
                    state["data"]["steps"]["step7_active_root_cause"] = next_root
                    self._save_state(project_id, state)
                    # ensure suggestions for next root
                    if not suggestions_by_root.get(next_root):
                        try:
                            s_data = await self._get_step7_countermeasures(
                                __request__,
                                __user__,
                                next_root,
                                process_ctx,
                                problem_spec,
                                current_metrics,
                                target_metrics,
                            )
                        except Exception as e:
                            s_data = {
                                "actions": [],
                                "llm_raw": "",
                                "llm_error": f"handler_error: {e}",
                            }
                        suggestions_by_root[next_root] = self._normalize_list(
                            s_data.get("actions") or [], limit=5
                        )
                        state["data"]["steps"]["step7_llm_raw"] = s_data.get("llm_raw", "")
                        state["data"]["steps"]["step7_llm_error"] = s_data.get("llm_error", "")
                        state["data"]["steps"]["step7_suggestions_by_root"] = suggestions_by_root
                        self._save_state(project_id, state)
                    next_suggestions = self._normalize_list(
                        suggestions_by_root.get(next_root) or [], limit=5
                    )
                    if not next_suggestions:
                        return (
                            "\u26a0\ufe0f \u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u043f\u043e\u043b\u0443\u0447\u0438\u0442\u044c \u0432\u0430\u0440\u0438\u0430\u043d\u0442\u044b \u043a\u043e\u043d\u0442\u0440\u043c\u0435\u0440 \u043e\u0442 LLM. "
                            "\u041f\u0440\u043e\u0432\u0435\u0440\u044c \u043c\u043e\u0434\u0435\u043b\u044c \u043c\u0435\u0442\u043e\u0434\u043e\u043b\u043e\u0433\u0430 \u0438\u043b\u0438 \u043f\u043e\u043f\u0440\u043e\u0431\u0443\u0439 \u0441\u043d\u043e\u0432\u0430: `\u043e\u0431\u043d\u043e\u0432\u0438 \u0432\u0430\u0440\u0438\u0430\u043d\u0442\u044b`.\n\n"
                            + _counter_prompt(
                                next_root,
                                next_suggestions,
                                prefix_msg="\u2705 \u041a\u043e\u043d\u0442\u0440\u043c\u0435\u0440\u044b \u0437\u0430\u0444\u0438\u043a\u0441\u0438\u0440\u043e\u0432\u0430\u043d\u044b. \u041f\u0435\u0440\u0435\u0445\u043e\u0434\u0438\u043c \u043a \u0441\u043b\u0435\u0434\u0443\u044e\u0449\u0435\u0439 \u043f\u0440\u0438\u0447\u0438\u043d\u0435.\n\n",
                            )
                        )
                    return _counter_prompt(
                        next_root,
                        next_suggestions,
                        prefix_msg="✅ Контрмеры зафиксированы. Переходим к следующей причине.\n\n",
                    )

                state["meta"]["step7_phase"] = "plan"
                self._save_state(project_id, state)
                phase = "plan"

            # phase: plan
            if phase == "plan":
                steps = state.get("data", {}).get("steps", {})
                actions = steps.get("step7_selected_actions", [])
                actions = self._normalize_list(actions or [], limit=15)
                if not actions:
                    state["meta"]["step7_phase"] = "countermeasures"
                    self._save_state(project_id, state)
                    return (
                        "⚠️ Нет выбранных контрмер. Давай выберем их заново.\n\n"
                        "Напиши: `обнови варианты`.\n\n"
                        "Команды: `/summary`, `/projects`, `/continue <ID>`, `/startnew <ID>`"
                    )

                plan = steps.get("step7_plan", [])
                if not plan:
                    try:
                        p_data = await self._get_step7_plan_from_actions(
                            __request__, __user__, actions, process_ctx
                        )
                    except Exception:
                        p_data = {"plan": []}
                    plan = p_data.get("plan") or []
                    if isinstance(plan, list):
                        plan = plan[:15]
                    else:
                        plan = []
                    state["data"]["steps"]["step7_plan"] = plan
                    self._save_state(project_id, state)

                t = (user_text or "").strip().lower()
                def _plan_warnings(items):
                    missing_owner = [i for i in items if not (i.get("owner") or "").strip()]
                    missing_due = [i for i in items if not (i.get("due") or "").strip()]
                    warnings = []
                    if missing_owner:
                        warnings.append("⚠️ Есть мероприятия без ответственного.")
                    if missing_due:
                        warnings.append("⚠️ Есть мероприятия без срока.")
                    return "\n".join(warnings)

                if t in {"ок", "окей", "готово", "подтверждаю", "да"}:
                    warnings = _plan_warnings(plan)
                    if warnings:
                        return _plan_prompt(plan, warnings=warnings)
                    state["meta"]["step7_phase"] = "done"
                    state["current_step"] = 8
                    self._save_state(project_id, state)
                    return (
                        "✅ Шаг 7 завершён.\n\n"
                        "План улучшений зафиксирован.\n\n"
                        "➡️ Следующий шаг (8) ещё не настроен: нет файла `step_8.json`.\n"
                        "Создай `step_8.json`, и продолжим.\n\n"
                        "Команды: `/summary`, `/projects`, `/continue <ID>`, `/startnew <ID>`"
                    )

                parsed = self._parse_plan_items(user_text)
                if not parsed:
                    return _plan_prompt(plan, warnings=_plan_warnings(plan))

                if len(parsed) > 15:
                    return (
                        "⚠️ План может содержать максимум 15 мероприятий. Сократи список и пришли снова.\n\n"
                        "Команды: `/summary`, `/projects`, `/continue <ID>`, `/startnew <ID>`"
                    )

                state["data"]["steps"]["step7_plan"] = parsed
                self._save_state(project_id, state)
                warnings = _plan_warnings(parsed)
                return _plan_prompt(
                    parsed,
                    prefix_msg="✅ План обновлён. Если всё ок, напиши: `ок`.\n\n",
                    warnings=warnings,
                )

        # ============== STEP >=4 (заглушка) ==============
        return (
            f"✅ Сохранено.\n\n"

            f"Текущий шаг: {current_step}\n"

            "Дальше расширим логику под следующий шаг.\n\n"

            "Команды: `/summary`, `/projects`, `/continue <ID>`, `/startnew <ID>`"

        )
