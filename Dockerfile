FROM python:3.13-alpine AS base

RUN apk update && apk upgrade


FROM base AS deps

COPY requirements.txt /tmp/
RUN apk add gcc musl-dev && mkdir /build && pip install --prefix /build -r /tmp/requirements.txt


FROM base AS final
ENV PYTHONPATH /am_bot
WORKDIR /am_bot

RUN adduser -D app
COPY --chown=app:app . .
COPY --from=deps /build /usr/local

USER app

ENTRYPOINT ["./entrypoint.sh"]
CMD ["run.py"]
