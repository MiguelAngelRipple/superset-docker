FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Para que el output de Python sea inmediato
ENV PYTHONUNBUFFERED=1

CMD ["python", "main.py"]
