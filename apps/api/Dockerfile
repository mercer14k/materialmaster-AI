FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml requirements-lock.txt LICENSE NOTICE ./
COPY src ./src
COPY apps/__init__.py ./apps/__init__.py
COPY apps/api ./apps/api
ARG INSTALL_SEMANTIC=false
RUN pip install --no-cache-dir 'pip>=26.2' && pip install --no-cache-dir -c requirements-lock.txt . && if [ "$INSTALL_SEMANTIC" = "true" ]; then pip install --no-cache-dir '.[semantic]'; fi \
    && useradd --create-home --uid 10001 appuser
USER appuser
EXPOSE 8000
CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
