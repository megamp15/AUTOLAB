# Photo Jobs. Built on the NAS by workflow 12's photos action, from this folder.
FROM python:3.12.16-alpine3.24

# ExifTool reads the recording dates. Nothing else is installed: the service is
# the Python standard library.
RUN apk add --no-cache exiftool

WORKDIR /app
COPY photo_jobs ./photo_jobs
COPY web ./web

ENV PYTHONUNBUFFERED=1 MEDIA_ROOT=/media STATE_DIR=/state PORT=8099
EXPOSE 8099
CMD ["python3", "-m", "photo_jobs.server"]
