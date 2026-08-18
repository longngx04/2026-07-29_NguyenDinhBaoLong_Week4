FROM python:3.12-slim
WORKDIR /srv
COPY app/requirements.txt ./requirements.txt
RUN python -m pip install --no-cache-dir -r requirements.txt
COPY . ./
RUN useradd --create-home --uid 10001 appuser && chown -R appuser /srv
USER appuser
CMD ["uvicorn", "gateway.main:app", "--host", "0.0.0.0", "--port", "9000"]
