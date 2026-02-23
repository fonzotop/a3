"""
title: Статус проекта
author: local
version: 0.3.1
required_open_webui_version: 0.8.0
"""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field


BASE_DIR = Path("/a3_assistant")
STATE_DIR = Path("/app/backend/data/a3_state/projects")
ACTIVE_DIR = Path("/app/backend/data/a3_state/active_users")


class Action:
    class Valves(BaseModel):
        DUMMY: str = Field(default="")

    def __init__(self):
        self.valves = self.Valves()

    def _extract_user_id(self, __user__) -> str:
        if isinstance(__user__, dict):
            return str(__user__.get("id", "unknown_user"))
        if isinstance(__user__, (list, tuple)) and __user__:
            first = __user__[0] if isinstance(__user__[0], dict) else {}
            return str(first.get("id", "unknown_user"))
        return "unknown_user"

    def _get_active_project(self, user_id: str) -> str:
        # 1) User's own active-project file (written by pipe on /continue or /new).
        if user_id and user_id != "unknown_user":
            p = ACTIVE_DIR / f"{user_id}.json"
            if p.exists():
                try:
                    data = json.loads(p.read_text(encoding="utf-8"))
                    pid = str(data.get("project_id", "")).strip()
                    if pid:
                        return pid
                except Exception:
                    pass
        # 2) Most recently modified project file (skip A3-0001 when real projects exist).
        files = list(STATE_DIR.glob("*.json"))
        if not files:
            return "A3-0001"
        real = [f for f in files if f.stem != "A3-0001"]
        pool = real if real else files
        return max(pool, key=lambda f: f.stat().st_mtime).stem

    def _load_state(self, project_id: str) -> dict[str, Any]:
        p = STATE_DIR / f"{project_id}.json"
        if not p.exists():
            state = {}
        else:
            try:
                state = json.loads(p.read_text(encoding="utf-8-sig"))
                if not isinstance(state, dict):
                    state = {}
            except Exception:
                state = {}
        state.setdefault("project_id", project_id)
        state.setdefault("current_step", 1)
        state.setdefault("meta", {})
        state.setdefault("data", {})
        if not isinstance(state["data"], dict):
            state["data"] = {}
        state["data"].setdefault("steps", {})
        state["data"].setdefault("raw", {})
        return state

    def _safe(self, value: Any) -> str:
        return html.escape(str(value or ""))

    def _status(self, step: int) -> str:
        if step >= 8:
            return "Completed"
        if step <= 1:
            return "Not Started"
        return "In Progress"

    def _join_nonempty(self, lines: list[str]) -> str:
        return "\n".join([x for x in lines if x.strip()])

    def _step1_problem(self, state: dict[str, Any]) -> str:
        steps = state["data"]["steps"]
        raw = state["data"]["raw"]
        return str(
            steps.get("raw_problem", {}).get("raw_problem_sentence", "") or raw.get("step_1", "")
        ).strip()

    def _step2_spec(self, state: dict[str, Any]) -> str:
        spec = state["data"]["steps"].get("problem_spec", {})
        if not isinstance(spec, dict):
            return str(state["data"]["raw"].get("step_2", "")).strip()
        lines = [
            f"Где/когда: {str(spec.get('where_when', '')).strip()}",
            f"Масштаб: {str(spec.get('scale', '')).strip()}",
            f"Последствия: {str(spec.get('consequences', '')).strip()}",
            f"Кто страдает: {str(spec.get('who_suffers', '')).strip()}",
            f"Деньги: {str(spec.get('money_impact', '')).strip()}",
        ]
        txt = self._join_nonempty(lines)
        return txt or str(state["data"]["raw"].get("step_2", "")).strip()

    def _step3_baseline(self, state: dict[str, Any]) -> str:
        metrics = state["data"]["steps"].get("current_state_metrics", [])
        lines: list[str] = []
        if isinstance(metrics, list):
            for item in metrics[:6]:
                if isinstance(item, dict):
                    m = str(item.get("metric", "")).strip()
                    v = str(item.get("current_value", item.get("value", ""))).strip()
                    if m and v:
                        lines.append(f"- {m}: {v}")
                    elif m:
                        lines.append(f"- {m}")
                else:
                    t = str(item).strip()
                    if t:
                        lines.append(f"- {t}")
        txt = self._join_nonempty(lines)
        return txt or str(state["data"]["raw"].get("step_4", "")).strip()

    def _step4_target(self, state: dict[str, Any]) -> str:
        metrics = state["data"]["steps"].get("target_state_metrics", [])
        lines: list[str] = []
        if isinstance(metrics, list):
            for item in metrics[:6]:
                if isinstance(item, dict):
                    m = str(item.get("metric", "")).strip()
                    v = str(item.get("target_value", item.get("value", ""))).strip()
                    if m and v:
                        lines.append(f"- {m}: {v}")
                    elif m:
                        lines.append(f"- {m}")
                else:
                    t = str(item).strip()
                    if t:
                        lines.append(f"- {t}")
        txt = self._join_nonempty(lines)
        return txt or str(state["data"]["raw"].get("step_5", "")).strip()

    def _step5_causes(self, state: dict[str, Any]) -> str:
        roots = state["data"]["steps"].get("root_causes", [])
        lines: list[str] = []
        if isinstance(roots, list):
            for item in roots[:6]:
                if isinstance(item, dict):
                    rc = str(item.get("root_cause", "")).strip()
                    if rc:
                        lines.append(f"- {rc}")
                else:
                    t = str(item).strip()
                    if t:
                        lines.append(f"- {t}")
        txt = self._join_nonempty(lines)
        if txt:
            return txt
        active = str(state["data"]["steps"].get("step6_active_problem", "")).strip()
        return active or str(state["data"]["raw"].get("step_6", "")).strip()

    def _step6_actions(self, state: dict[str, Any]) -> str:
        steps = state["data"]["steps"]
        plan = steps.get("step7_plan", [])
        lines: list[str] = []
        if isinstance(plan, list):
            for p in plan[:6]:
                if not isinstance(p, dict):
                    continue
                action = str(p.get("action", "")).strip()
                owner = str(p.get("owner", "")).strip()
                due = str(p.get("due", "")).strip()
                tail = ", ".join([x for x in [owner, due] if x])
                if action:
                    lines.append(f"- {action}" + (f" ({tail})" if tail else ""))
        txt = self._join_nonempty(lines)
        if txt:
            return txt
        selected = steps.get("step7_selected_actions", [])
        if isinstance(selected, list):
            rows = [f"- {str(x).strip()}" for x in selected[:6] if str(x).strip()]
            txt = self._join_nonempty(rows)
            if txt:
                return txt
        return str(state["data"]["raw"].get("step_7", "")).strip()

    def _step7_monitoring(self, state: dict[str, Any]) -> str:
        raw = str(state["data"]["raw"].get("step_8", "")).strip()
        approval = str(state.get("meta", {}).get("approval_status", "")).strip()
        lines = []
        if approval:
            lines.append(f"Approval: {approval}")
        if raw:
            lines.append(raw)
        return self._join_nonempty(lines)

    def _process_meta(self, state: dict[str, Any], project_id: str) -> dict[str, str]:
        steps = state["data"]["steps"]
        process_ctx = steps.get("process_context", {}) if isinstance(steps.get("process_context", {}), dict) else {}
        process_def = steps.get("process_definition", {}) if isinstance(steps.get("process_definition", {}), dict) else {}
        process_data = state["data"].get("process", {}) if isinstance(state["data"].get("process", {}), dict) else {}
        process_final = process_data.get("final", {}) if isinstance(process_data.get("final", {}), dict) else {}

        project_title = (
            str(process_ctx.get("project_title", "")).strip()
            or str(process_def.get("project_title", "")).strip()
            or str(process_final.get("project_title", "")).strip()
            or str(project_id).strip()
        )
        process_name = (
            str(process_ctx.get("process_name", "")).strip()
            or str(process_def.get("process_name", "")).strip()
            or str(process_final.get("process_name", "")).strip()
        )
        boundary_start = (
            str(process_ctx.get("start_event", "")).strip()
            or str(process_final.get("boundary_start", "")).strip()
        )
        boundary_end = (
            str(process_ctx.get("end_event", "")).strip()
            or str(process_final.get("boundary_end", "")).strip()
        )
        perimeter = str(process_ctx.get("perimeter", "")).strip()
        owner = (
            str(process_ctx.get("owner", "")).strip()
            or str(process_final.get("process_owner", "")).strip()
        )
        return {
            "project_title": project_title,
            "process_name": process_name,
            "boundary_start": boundary_start,
            "boundary_end": boundary_end,
            "perimeter": perimeter,
            "owner": owner,
            "customer": "Генеральный директор",
        }

    def _debug_info(self, user_id: str) -> str:
        active_p = ACTIVE_DIR / f"{user_id}.json"
        active_exists = active_p.exists()
        active_content = ""
        if active_exists:
            try:
                active_content = active_p.read_text(encoding="utf-8")[:80]
            except Exception as e:
                active_content = str(e)
        files = list(STATE_DIR.glob("*.json"))
        mtimes = sorted([(f.stem, round(f.stat().st_mtime)) for f in files], key=lambda x: -x[1])[:5]
        return (
            f"uid={user_id[:16]} | "
            f"active={'Y:' + active_content if active_exists else 'N'} | "
            f"mt={mtimes}"
        )

    async def action(
        self,
        body: dict,
        __user__=None,
        __event_emitter__=None,
        __event_call__=None,
        __metadata__=None,
        __request__=None,
    ) -> Optional[dict]:
        user_id = self._extract_user_id(__user__)
        project_id = self._get_active_project(user_id)
        _dbg = self._debug_info(user_id)
        state = self._load_state(project_id)
        step = int(state.get("current_step", 1))
        meta = self._process_meta(state, project_id)

        step_titles = {
            1: "Проблема",
            2: "Уточнение проблемы",
            3: "Текущее состояние",
            4: "Целевое состояние",
            5: "Причины",
            6: "Причины",
            7: "Мероприятия",
            8: "Мониторинг",
        }
        step_name = step_titles.get(step, f"Шаг {step}")

        card_values = [
            ("1. Проблема", self._step1_problem(state)),
            ("2. Уточнение проблемы", self._step2_spec(state)),
            ("3. Текущее состояние", self._step3_baseline(state)),
            ("4. Целевое состояние", self._step4_target(state)),
            ("5. Причины", self._step5_causes(state)),
            ("6. Мероприятия", self._step6_actions(state)),
            ("7. Мониторинг", self._step7_monitoring(state)),
        ]
        card_map = {title: text for title, text in card_values}

        def render_card(title: str, text: str, min_h: int = 120) -> str:
            value = self._safe(text).replace("\n", "<br>") or "Нет данных"
            return (
                f'<div style="background:#fff;border:1px solid #c7d4e5;'
                f'border-radius:10px;padding:10px;min-height:{min_h}px;">'
                f'<div style="font-weight:700;color:#10243a;margin-bottom:6px;">{self._safe(title)}</div>'
                f'<div style="font-size:13px;color:#25384f;line-height:1.45;">{value}</div>'
                f"</div>"
            )

        row1 = [
            render_card("1. Проблема", card_map.get("1. Проблема", "")),
            render_card("2. Уточнение проблемы", card_map.get("2. Уточнение проблемы", "")),
            render_card("3. Текущее состояние", card_map.get("3. Текущее состояние", "")),
            render_card("4. Целевое состояние", card_map.get("4. Целевое состояние", "")),
        ]
        row2 = [
            render_card("5. Причины", card_map.get("5. Причины", "")),
            render_card("6. Мероприятия", card_map.get("6. Мероприятия", ""), min_h=180),
            render_card("7. Мониторинг", card_map.get("7. Мониторинг", "")),
        ]

        boundaries = (
            f"{meta.get('boundary_start','')} -> {meta.get('boundary_end','')}"
            if (meta.get("boundary_start") or meta.get("boundary_end"))
            else ""
        )

        html_block = f"""```html
<!-- OPENWEBUI_PLUGIN_OUTPUT -->
<div style="font-family:Inter,Arial,sans-serif;background:#eef3f8;border:1px solid #c6d3e6;border-radius:12px;padding:12px;">
  <div style="background:linear-gradient(90deg,#eaf2ff,#f4f8ff);border:1px solid #c6d3e6;border-radius:10px;padding:10px 12px;margin-bottom:10px;">
    <div style="font-size:18px;font-weight:700;color:#10243a;">A3 Project: {self._safe(meta.get("project_title",""))} | Шаг {step}: {self._safe(step_name)}</div>
    <div style="font-size:14px;color:#243a52;margin-top:4px;">Статус: {self._safe(self._status(step))}</div>
    <div style="font-size:13px;color:#1f3550;margin-top:8px;">
      Название процесса: {self._safe(meta.get("process_name","")) or "Нет данных"} |
      Границы: {self._safe(boundaries) or "Нет данных"} |
      Периметр: {self._safe(meta.get("perimeter","")) or "Нет данных"} |
      Владелец процесса: {self._safe(meta.get("owner","")) or "Нет данных"} |
      Заказчик проекта: {self._safe(meta.get("customer",""))}
    </div>
  </div>
  <div style="display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-bottom:10px;">
    {''.join(row1)}
  </div>
  <div style="display:grid;grid-template-columns:1fr 2fr 1fr;gap:10px;">
    {''.join(row2)}
  </div>
  <div style="font-size:10px;color:#888;margin-top:6px;word-break:break-all;">DBG: {self._safe(_dbg)}</div>
</div>
```"""

        content = "\n\n" + html_block + "\n"

        if __event_emitter__:
            try:
                await __event_emitter__(
                    {
                        "type": "message",
                        "data": {"content": content},
                    }
                )
            except Exception:
                pass

        return {
            "content": content,
            "messages": [{"role": "assistant", "content": content}],
        }
