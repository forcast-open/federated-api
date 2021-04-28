# Federated Api

Dockerized service for the server side implementarion of an Api for Federated Learning, with client simulation examples.

## Set up.

Since it's a bit tricky to get all the dependencies set up just right, there are Dockerfiles and a Compose file provided in this repo. The Dockerfiles contains instructions on how to build the docker images, while the Compose file contains instructions on how to run the images as a service.

1. [Install Docker](https://docs.docker.com)
2. [Install Docker Compose](https://docs.docker.com/compose/install/)
3. [Install Nvidia-Docker](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html#docker)
4. Run, <code>git clone https://github.com/forcast-lmtd/federated-api.git</code>
5. Run, <code>cd federated-api</code> to work inside the downloaded repository.

You should end up with the folder structure:

    .
    └── federated-api
        ├── app
        ├── celery-queue
        ├── client 
        └── ...

## Build the Docker service.

<pre class="prettyprint lang-bsh">
<code class="devsite-terminal tfo-terminal-venv">sudo docker-compose build</code>
</pre>

## Run the dockerized app.

<pre class="prettyprint lang-bsh">
<code class="devsite-terminal tfo-terminal-venv">sudo docker-compose run</code>
</pre>

## Test with a client

Go into the <code>client</code> folder.

## Build the Docker service for the client test.

<pre class="prettyprint lang-bsh">
<code class="devsite-terminal tfo-terminal-venv">sudo docker-compose build</code>
</pre>

## Run the dockerized client app.

<pre class="prettyprint lang-bsh">
<code class="devsite-terminal tfo-terminal-venv">sudo docker-compose run</code>
</pre>

This code will create, allocate and simulate ten clients to participate in a federated training procedure. To run this successfully the server side docker-compose must also be runing.

In case the client simulation stops unexpectedly, in the server docker run <code>sudo rm -r postgres_data</code> to delete the local postgres database to allow the reallocation the new clients.


