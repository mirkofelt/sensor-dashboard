FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/

ENV INFLUX_HOST=""
ENV INFLUX_PORT="8086"
ENV INFLUX_TOKEN=""
ENV INFLUX_ORG=""
ENV INFLUX_BUCKET="sensors"

EXPOSE 8000

CMD ["uvicorn", "app:app", "--app-dir", "src", "--host", "0.0.0.0", "--port", "8000"]
