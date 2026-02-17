"""
title: A3 Workflow Buttons
author: local
version: 0.1.0
required_open_webui_version: 0.8.0
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


BASE_DIR = Path("/a3_assistant")
STATE_DIR = BASE_DIR / "state" / "projects"
ACTIVE_DIR = BASE_DIR / "state" / "active_users"


class Action:
    async def _emit_follow_ups(self, __event_emitter__, items: List[str]) -> None:
        if not __event_emitter__ or not items:
            return
        await __event_emitter__(
            {"type": "chat:message:follow_ups", "data": {"follow_ups": items}}
        )

    def _extract_user_id(self, __user__) -> str:
        if isinstance(__user__, dict):
            return str(__user__.get("id", "unknown_user"))
        if isinstance(__user__, (list, tuple)) and __user__:
            first = __user__[0] if isinstance(__user__[0], dict) else {}
            return str(first.get("id", "unknown_user"))
        return "unknown_user"

    def _get_active_project(self, user_id: str) -> str:
        p = ACTIVE_DIR / f"{user_id}.json"
        if not p.exists():
            return "A3-0001"
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            project_id = str(data.get("project_id", "")).strip()
            return project_id or "A3-0001"
        except Exception:
            return "A3-0001"

    def _load_state(self, project_id: str) -> Dict[str, Any]:
        p = STATE_DIR / f"{project_id}.json"
        if not p.exists():
            return {"current_step": 1, "meta": {}, "data": {}}
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return {"current_step": 1, "meta": {}, "data": {}}

    def _step_actions(self, step: int) -> List[str]:
        # String follow-ups are supported by OpenWebUI v0.8.x and clickable in chat.
        primary = ["🔁 ОБНОВИТЬ ВАРИАНТЫ"]
        if step == 3:
            return primary
        if step == 4:
            return primary
        if step == 6:
            return primary
        return primary

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
        state = self._load_state(project_id)
        step = int(state.get("current_step", 1))

        actions = self._step_actions(step)
        await self._emit_follow_ups(__event_emitter__, actions)

        return {
            "messages": [
                {
                    "role": "assistant",
                    "content": (
                        f"Кнопки workflow обновлены для проекта `{project_id}` "
                        f"(шаг {step}). Выбери действие ниже в блоке «Продолжить»."
                    ),
                }
            ]
        }
