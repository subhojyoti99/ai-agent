# Use an official lightweight Python image
FROM python:3.9-slim

# Set working directory inside container
WORKDIR /app

# Prevent Python from writing .pyc files & buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Copy requirements and install dependencies
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose the FastAPI port (changed from 8080 to 9030)
EXPOSE 8080

# Command to run the app with uvicorn on port 9030
# If your FastAPI instance is named `app` inside voice_agent.py
CMD ["uvicorn", "voice_agent:app", "--host", "0.0.0.0", "--port", "8080"]
