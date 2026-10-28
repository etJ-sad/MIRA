FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY mira ./mira
RUN pip install --no-cache-dir .
ENV MIRA_DATA_DIR=/data
VOLUME /data
EXPOSE 8080
CMD ["mira", "serve", "--port", "8080"]
