# AI Video Assistant -- PDF-only deployment image (Hugging Face Spaces, Docker SDK)
#
# Python 3.14 matches the version the app was developed and tested on.

FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/home/user/.cache/huggingface \
    ENABLE_VIDEO=false \
    LOG_TO_FILE=false

# Hugging Face runs containers as a non-root user with id 1000.
RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:$PATH"
WORKDIR /home/user/app

# 1) Dependencies first (cached unless requirements change).
COPY --chown=user requirements-deploy.txt .
RUN pip install --no-cache-dir --user torch==2.13.0 --index-url https://download.pytorch.org/whl/cpu \
 && pip install --no-cache-dir --user -r requirements-deploy.txt

# 2) Download the embedding model now, so the first PDF analysis doesn't have
#    to fetch it at runtime.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# 3) The app itself.
COPY --chown=user . .
RUN mkdir -p data vector_db logs

EXPOSE 7860

# XSRF protection is turned off because the Space page embeds the app in an
# iframe, which otherwise makes file uploads fail with a 403 error.
CMD ["streamlit", "run", "app.py", \
     "--server.port=7860", \
     "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--server.enableXsrfProtection=false", \
     "--server.enableCORS=false", \
     "--browser.gatherUsageStats=false"]
