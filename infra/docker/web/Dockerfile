FROM python:3.12-slim

ARG OPENGREP_URL=https://github.com/opengrep/opengrep/releases/download/v1.26.0/opengrep_manylinux_x86
ARG OPENGREP_SHA256=40c21299eeddabf743b856daa843d24f9d4a027130671cd45b3b21776fd9ab26

RUN apt-get update \
    && apt-get install --yes --no-install-recommends ca-certificates curl jq \
    && curl --fail --location --retry 5 --retry-all-errors \
      --connect-timeout 30 --max-time 600 \
      --output /tmp/opengrep "$OPENGREP_URL" \
    && echo "$OPENGREP_SHA256  /tmp/opengrep" | sha256sum --check --status \
    && install --mode=0755 /tmp/opengrep /usr/local/bin/opengrep \
    && rm -rf /var/lib/apt/lists/* /tmp/opengrep

WORKDIR /app

COPY requirements.txt pyproject.toml ./
COPY src ./src
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY configs ./configs
COPY schemas ./schemas
COPY data ./data
COPY scripts ./scripts
COPY benchmarks ./benchmarks

EXPOSE 8000
CMD ["uvicorn", "project_sentinel.web.main:app", "--host", "0.0.0.0", "--port", "8000"]
