FROM python:3.6.9

RUN mkdir -p /src
WORKDIR /src

COPY Dockerfile .
COPY requirements.txt .

# install requirements
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# For checking other containers
ENV DOCKERIZE_VERSION v0.6.1
RUN wget https://github.com/jwilder/dockerize/releases/download/$DOCKERIZE_VERSION/dockerize-linux-amd64-$DOCKERIZE_VERSION.tar.gz \
    && tar -C /usr/local/bin -xzvf dockerize-linux-amd64-$DOCKERIZE_VERSION.tar.gz \
    && rm dockerize-linux-amd64-$DOCKERIZE_VERSION.tar.gz

# expose the app port
EXPOSE 5000