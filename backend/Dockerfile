# Verity backend (Django) application image.
FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    DJANGO_SETTINGS_MODULE=verity.settings.development

WORKDIR /app

# Install dependencies first so the layer is cached across code changes.
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Application source (includes manage.py and entrypoint.sh).
COPY . /app
RUN chmod +x /app/entrypoint.sh

EXPOSE 8000

# The entrypoint waits for the DB, migrates, seeds, and provisions the
# admin before handing off to the command below. Invoked via bash so it
# works even when a dev bind-mount shadows the image's executable bit.
ENTRYPOINT ["bash", "/app/entrypoint.sh"]
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
