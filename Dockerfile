# Use official Python image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y build-essential && rm -rf /var/lib/apt/lists/*

# Copy Python dependencies first
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project folders
COPY backend ./backend
COPY src ./src
COPY vectorStore ./vectorStore

# Expose FastAPI port
EXPOSE 8000

# Run FastAPI app
CMD ["uvicorn", "backend.api:app", "--host", "0.0.0.0", "--port", "8000"]
