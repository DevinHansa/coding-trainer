FROM python:3.11-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Expose port
EXPOSE 5000

# Start server using the port assigned by Railway
CMD ["sh", "-c", "gunicorn app:app --bind 0.0.0.0:$PORT"]
