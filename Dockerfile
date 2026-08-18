FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot.py llm_client.py tools.py commands.py ./

# No EXPOSE needed — this is a Discord gateway client (outbound WebSocket +
# HTTPS only), not a web server. Nothing to serve on a port.

CMD ["python", "bot.py"]
