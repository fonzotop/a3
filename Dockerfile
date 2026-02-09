FROM ghcr.io/open-webui/open-webui:main

# Папка с вашим A3 ассистентом
COPY a3_assistant /a3_assistant

# Пайплайн в каталог OpenWebUI
COPY openwebui_data/pipelines/a3_controller.py /app/backend/data/pipelines/a3_controller.py

ENV PORT=80
EXPOSE 80
