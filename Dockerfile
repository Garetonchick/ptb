FROM python:3.11.4-alpine3.17
WORKDIR /ptb
RUN apk update
RUN apk add --no-cache bash
RUN apk add --no-cache postgresql-dev gcc musl-dev
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["bash", "-c", "./entrypoint.sh"]
