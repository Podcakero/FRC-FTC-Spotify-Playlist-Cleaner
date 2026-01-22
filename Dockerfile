FROM python:3.10-alpine AS builder

WORKDIR /app

COPY app/requirements.txt /app
RUN --mount=type=cache,target=/root/.cache/pip \
    pip3 install -r requirements.txt

COPY /app /app

ENTRYPOINT ["python3"]
CMD ["-m", "flask", "run", "--debug", "--host=0.0.0.0"]