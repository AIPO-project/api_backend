FROM python:3.11-slim

# flask-mysqldb usa o mysqlclient, que precisa compilar contra a libmysqlclient
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc pkg-config default-libmysqlclient-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY api.py .

EXPOSE 5000

# api.py não tem app.run(); o gunicorn importa o objeto "app" do módulo "api"
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "60", "api:app"]
