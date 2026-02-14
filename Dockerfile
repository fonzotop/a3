FROM ghcr.io/open-webui/open-webui:v0.8.1

COPY a3_assistant /a3_assistant
COPY openwebui_data/pipelines/a3_controller.py /app/backend/data/pipelines/a3_controller.py

RUN chmod +x /a3_assistant/scripts/start_with_sync.sh

EXPOSE 8080

CMD ["bash", "/a3_assistant/scripts/start_with_sync.sh"]
