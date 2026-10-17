FROM python:3.12-slim

ARG WITH_ML=1
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    HF_HOME=/opt/hf-cache

WORKDIR /app
COPY pyproject.toml ./
RUN mkdir -p app && touch app/__init__.py \
 && if [ "$WITH_ML" = "1" ]; then \
      pip install --index-url https://download.pytorch.org/whl/cpu torch \
      && pip install -e ".[ml]" \
      && python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"; \
    else pip install -e . ; fi

COPY . .
RUN useradd --create-home app && chown -R app /app /opt/hf-cache 2>/dev/null || true
USER app
EXPOSE 8004
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8004"]
