FROM ghcr.io/open-webui/open-webui:v0.8.1

# Папка с вашим A3 ассистентом
COPY a3_assistant /a3_assistant

# Пайплайн в каталог OpenWebUI
COPY openwebui_data/pipelines/a3_controller.py /app/backend/data/pipelines/a3_controller.py

EXPOSE 8080
