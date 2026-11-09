FROM golang:1.26-alpine3.22 AS build
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY main.go index.html ./
RUN CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /qr .

FROM alpine:3.22
# Its own unprivileged account; /data is the one place it writes.
RUN adduser -D -H -u 10001 qr && mkdir /data && chown qr /data
USER qr
COPY --from=build /qr /qr
EXPOSE 8080 8081
ENTRYPOINT ["/qr"]
