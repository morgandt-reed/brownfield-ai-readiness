FROM golang:1.22 AS build
WORKDIR /src
COPY . .
RUN go build -o /notify-worker ./...

FROM gcr.io/distroless/base
COPY --from=build /notify-worker /notify-worker
ENTRYPOINT ["/notify-worker"]
