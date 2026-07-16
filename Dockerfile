FROM python:3.11-slim

WORKDIR /app

RUN pip install poetry

COPY pyproject.toml poetry.lock ./
RUN poetry config virtualenvs.create false && poetry install --no-root --only main

COPY . .

CMD ["uvicorn", "meridian.main:app", "--host", "0.0.0.0", "--port", "8000"]
