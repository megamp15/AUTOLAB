FROM python:3.13-alpine3.22
# Standard library only: nothing to install, nothing to pin but the base.
# Its own unprivileged account; /data is the one place it writes.
RUN adduser -D -H -u 10001 rdapi && mkdir /data && chown rdapi /data
USER rdapi
WORKDIR /app
COPY server.py .
ENV RUSTDESK_API_DB=/data/rustdesk-api.db PYTHONUNBUFFERED=1
VOLUME /data
EXPOSE 21114
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request as u; u.urlopen('http://127.0.0.1:21114/api/login-options')"
ENTRYPOINT ["python", "/app/server.py"]
CMD ["serve"]
