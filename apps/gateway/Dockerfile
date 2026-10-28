FROM python:3.12.13-slim AS builder
WORKDIR /build
COPY apps/gateway/requirements.lock ./
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.lock
COPY apps/gateway/pyproject.toml ./
COPY apps/gateway/src ./src
RUN pip wheel --no-deps --wheel-dir /wheels .

FROM python:3.12.13-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN groupadd --gid 10001 tollgate && useradd --uid 10001 --gid tollgate --create-home tollgate
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir --no-index --find-links=/wheels tollgate && rm -rf /wheels
WORKDIR /app
COPY config /app/config
USER tollgate
EXPOSE 8187
HEALTHCHECK --interval=15s --timeout=3s CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8187/healthz')"
ENTRYPOINT ["tollgate"]
CMD ["serve"]
