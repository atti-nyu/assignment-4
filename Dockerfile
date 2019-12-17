FROM ubuntu:16.04

#MAINTANER Atticus 

RUN apt-get update -y && \
    apt-get install -y python-pip python-dev

COPY . /app ./requirements.txt /app/requirements.txt
WORKDIR /app

RUN pip install -r requirements.txt

EXPOSE 8080

ENTRYPOINT ["/bin/sh"]

CMD ["/app/boot.sh"]