# syntax=docker/dockerfile:1.7
FROM python:3.12-slim-bookworm AS runtime
ARG VCS_REF=unknown
ARG VERSION=0.1.0
ARG BUILD_DATE=unknown
LABEL org.opencontainers.image.title="sample-container-app" \
      org.opencontainers.image.description="Code Clinic multi-architecture supply-chain demo" \
      org.opencontainers.image.source="https://example.invalid/example/multiarch-container-security-pipeline" \
      org.opencontainers.image.revision="$VCS_REF" \
      org.opencontainers.image.version="$VERSION" \
      org.opencontainers.image.created="$BUILD_DATE" \
      org.opencontainers.image.licenses="MIT"
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 APP_PORT=8080
WORKDIR /app
COPY --chown=10001:10001 app/ ./app/
USER 10001:10001
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=2)"
ENTRYPOINT ["python", "-m", "app.main"]
