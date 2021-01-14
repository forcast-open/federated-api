FROM python:3.6.9

COPY . /client
WORKDIR /client

# install requirements
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# run the client
CMD ["python", "client.py"]
