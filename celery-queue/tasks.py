# Imports
import os
import time
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import jsonpickle as jspk
# Celary asynchronus task imports
from celery import Celery
from datetime import timedelta, datetime
# Federated imports
import forcast_federated_learning as ffl
import uuid
# Database imports
from utils.models import ClientsData, ServerData
from utils.worker import app, celery, db

# Parameters
SERVER_ID = 0



#### Celery configuration ####



celery.conf.beat_schedule = {
	'Check clients updates': {
		'task': 'tasks.check_clients_update',
		'schedule': timedelta(milliseconds=1_000)
		}
	}
celery.conf.timezone = 'UTC'



#### Federated Model ####



# Create federated model based on a pytorch model
num_features, num_classes = 4,3
model = ffl.models.NN(input_dim=num_features, output_dim=num_classes) # pytorch model
fed_model = ffl.FederatedModel(model, model_type='nn')



#### Periodic tasks ####



@celery.task(name ='tasks.check_clients_update')
def periodic_task():
	# Check there is server data
	server_data   = ServerData.query.filter_by(server_id=SERVER_ID).first()
	server_com_id = server_data.com_round_id
	if not server_data: # if server not found (result == None) return error
		return {'message': f'Could not find server with id {SERVER_ID}'}
	
	# Check the state of the server
	if server_data.state == 'updated':
		return {'message': f'Server {SERVER_ID} is already updated'}
	
	# Check client database
	
	# Total number of clients in the database
	clients_all     = ClientsData.query.all()
	n_clients       = len( clients_all )
	# Ready clients: Ones that have updated their models to the database and are in the same comunication round as the server
	clients_ready   = ClientsData.query.filter_by(state='updated').filter_by(com_round_id=server_com_id).all()
	k_ready_clients = len( clients_ready )

	# Check existance of at least one client
	if n_clients == 0:
		return {'message': f'Could not find clients in the database'}

	percentage_of_ready_clients = 100 * k_ready_clients / n_clients
	if percentage_of_ready_clients < 50:
		return {'message': f'{k_ready_clients} / {n_clients} ready clients not enough'}


	## Else: Everything ok ##
	

	messages = []
	messages.append(f'{k_ready_clients} / {n_clients} ready clients, starting federated update')
	new_server_com_id = uuid.uuid1()

	# Get the client weights and local data length for the federated aggregation
	client_weights = []
	client_lens    = []
	# Iterate over clients database rows
	for client_data in clients_ready:
		client_weights.append( jspk.decode(client_data.weights) )
		client_lens.append( client_data.data_len )
	
	## Update fedearted model ##

	fed_model.server_agregate(client_weights, client_lens)
	weights = jspk.encode(fed_model.state_dict())

	# Update server database
	server_data.weights       = weights
	server_data.state         = 'waiting'
	server_data.com_round_id  = new_server_com_id # new comunication round
	server_data.last_modified = datetime.utcnow()
	db.session.commit()
	messages.append(f'Update of server with id {SERVER_ID}, successful')

	## Update the clients ##
	for client_data in clients_ready:
		client_data.weights       = weights
		client_data.state         = 'iddle'
		client_data.com_round_id  = new_server_com_id
		client_data.last_modified = datetime.utcnow()
		db.session.commit()

	return {'messages': messages, 'new communication round id': f'{new_server_com_id}'}



#### Async tasks ####



@celery.task(name='tasks.database_init')
def database_init():
	# Initialize the database if it does not exist
	messages = []

	if not db.engine.table_names():
		db.create_all()
		db.session.commit()
		messages.append('Database initialized')

	if not ServerData.query.all():
		weights      = fed_model.state_dict()
		com_round_id = uuid.uuid1()
		server = ServerData(server_id=SERVER_ID, state='waiting', weights=jspk.encode(weights), com_round_id=com_round_id, last_modified = datetime.utcnow())
		client = ClientsData(client_id=0       , state='iddle'  , weights=jspk.encode(weights), com_round_id=com_round_id, last_modified = datetime.utcnow(), data_len=1)
		db.session.add(server)
		db.session.add(client)
		db.session.commit()
		messages.append('Database loaded')

	if not messages:
		messages.append('Already initialized')
	
	return {'messages': messages}