# Use 3.13-slim for a balance of features and size
FROM python:3.13-slim

# Prevent python from writing pyc files and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies if you use databases like PostgreSQL
# RUN apt-get update && apt-get install -y libpq-dev gcc && rm -rf /var/lib/apt/lists/*

# Copy only the files needed for installation first to leverage cache
COPY pyproject.toml README.md ./
# If you have a requirements.txt instead, use: COPY requirements.txt .

# Install dependencies. Remove -e if you don't need "hot-reloading" for the code structure itself.
RUN pip install --no-cache-dir .[dev]

# Copy the rest of the application
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini ./alembic.ini

EXPOSE 8000

# Using JSON syntax for CMD is preferred
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]