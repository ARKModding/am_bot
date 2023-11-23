FROM python:3-alpine as base
WORKDIR /app
RUN apk update --no-cache && apk add --no-cache gcc musl-dev
COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

FROM base
COPY run.py run.py
COPY am_bot am_bot
ENTRYPOINT ["python", "run.py"]
