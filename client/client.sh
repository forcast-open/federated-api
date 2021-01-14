# sudo docker build -t client .
sudo docker run -it -v "/home/lfgarcia1/Documents/TT/Repos/Forcast-Federated-Learning/forcast_federated_learning/:/client/forcast_federated_learning/" --network="host" client
