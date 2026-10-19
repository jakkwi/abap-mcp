FROM python:3.13-slim

# Node.js powers the optional lint and run_tests tools.
RUN apt-get update \
    && apt-get install -y --no-install-recommends nodejs npm \
    && npm install --global @abaplint/cli@2 \
    && rm -rf /var/lib/apt/lists/* /root/.npm

RUN useradd --create-home --uid 1000 abap
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir .

USER abap
VOLUME /workspace
EXPOSE 8000
ENTRYPOINT ["abap-mcp", "--root", "/workspace", "--http", "--host", "0.0.0.0", "--port", "8000"]
