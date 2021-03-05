# Imports
import os
import time
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import jsonpickle as jspk
# Celary asynchronus task imports
from celery import Celery
from celery.task.control import inspect
from datetime import timedelta, datetime
# Federated imports
import forcast_federated_learning as ffl
import uuid
# Database imports
from utils.models import ClientsData, ServerData
from utils.worker import app, celery, db

# Parameters
SERVER_ID                          = int( os.environ.get('SERVER_ID') )
seed                               = int( os.environ.get('SEED') )
k_ready_clients_needed             = 5
percentage_of_ready_clients_needed = 100



#### Celery configuration ####



celery.conf.beat_schedule = {
	'Check clients updates': {
		'task': 'tasks.check_clients_update',
		'schedule': timedelta(milliseconds=5_000)
		}
	}
celery.conf.timezone = 'UTC'



#### Federated Model ####



# Create federated model based on a pytorch model
num_features, num_classes = 4, 3
model           = ffl.models.NN(input_dim=num_features, output_dim=num_classes, init_seed=seed) # pytorch model
fed_model       = ffl.FederatedModel(model, model_type='nn')

# Create secret and public key for encryption
public_context, secret_key = ffl.encryption.get_context(seed=seed)

# # bool variable to check if the federated update is already running
# running_fed_update = False



#### Periodic tasks ####



@celery.task(name ='tasks.check_clients_update')
def check_clients_update():
	# Check if there's server data in the database
	if not db.engine.table_names():
		return {'message': f'No server table in the database'}
	if not ServerData.query.all():
		return {'message': f'No server data in the database table'}

	# Check there is server data
	server_data   = ServerData.query.filter_by(server_id=SERVER_ID).first()
	if not server_data: # if server not found (result == None) return error
		return {'message': f'Could not find server with id {SERVER_ID}'}
	server_com_id = server_data.com_round_id
	
	# Check the state of the server
	if server_data.state == 'updated':
		return {'message': f'Server {SERVER_ID} is already updated'}
	
	# Check client database
	
	# Total number of clients in the database
	clients_all     = ClientsData.query.all()
	n_clients       = len( clients_all )
	# Check existance of at least one client
	if n_clients == 0:
		return {'message': f'Could not find clients in the database'}
	
	# Ready clients: Ones that have updated their models to the database and are in the same comunication round as the server
	clients_ready   = ClientsData.query.filter_by(state='updated').filter_by(com_round_id=server_com_id).all()
	k_ready_clients = len( clients_ready )

	percentage_of_ready_clients = 100 * k_ready_clients / n_clients
	if k_ready_clients < k_ready_clients_needed: # percentage_of_ready_clients < percentage_of_ready_clients_needed:
		return {'message': f'{k_ready_clients} / {n_clients} ready clients not enough'}

	## Else: Everything ok ##
	
	messages = []
	messages.append(f'{k_ready_clients} / {n_clients} ready clients, starting federated update')
	new_server_com_id = uuid.uuid1()
	print(1)
	# Get the client weights and local data length for the federated aggregation
	client_weights = []
	client_lens    = []
	# Iterate over clients database rows
	for client_data in clients_ready:
		enc_weights = jspk.decode(client_data.weights) 
		enc_weights = ffl.encryption.EncStateDict.load(public_context, enc_weights)
		client_weights.append( enc_weights )
		client_lens.append( client_data.data_len )
		
	## Update fedearted model ##
	print(2)
	fed_model.server_agregate(client_weights, client_lens, secret_key=secret_key)
	weights = jspk.encode(fed_model.state_dict())
	print(3)
	# Update server database
	server_data.weights       = weights
	server_data.state         = 'waiting'
	server_data.com_round_id  = new_server_com_id # new comunication round
	server_data.last_modified = datetime.utcnow()
	db.session.commit()
	messages.append(f'Update of server with id {SERVER_ID}, successful')
	print(4)
	## Update the clients ##
	for client_data in clients_ready:
		client_data.state         = 'iddle'
		client_data.last_modified = datetime.utcnow()
		db.session.commit()
	print(5)
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
		server = ServerData(server_id     = SERVER_ID, 
							state         = 'waiting', 
							weights       = jspk.encode(weights), 
							com_round_id  = com_round_id, 
							last_modified = datetime.utcnow(), 
							context       = jspk.encode(public_context.serialize())
							)
		db.session.add(server)
		db.session.commit()
		messages.append('Database loaded')

	if not messages:
		messages.append('Already initialized')
	
	return {'messages': messages}



@celery.task(name='tasks.reset_server_weights')
def reset_server_weights(server_id):
	# Reset the server weights to an untrained state and set a new comunication round
	com_round_id    = uuid.uuid1()
	initial_weights = model.init_weights(init_seed=seed).state_dict()
	update_dict     = {'state':'waiting', 'weights':jspk.encode(initial_weights), 'com_round_id':com_round_id, 'last_modified':datetime.utcnow()}
	server          = ServerData.query.filter_by(server_id=server_id).update(update_dict)
	db.session.commit()
	
	return {'message': 'Reset of server state successful.', 'server_id': server_id}



@celery.task(name='tasks.reset_client_weights')
def reset_client_weights(client_id):
	# Reset the client weights to an untrained state
	initial_weights = model.init_weights(init_seed=seed).state_dict()
	update_dict     = {'state':'iddle', 'weights':jspk.encode(initial_weights), 'com_round_id':'', 'last_modified':datetime.utcnow()}
	client          = ClientsData.query.filter_by(client_id=client_id).update(update_dict)
	db.session.commit()
	
	return {'message': 'Reset of client state successful.', 'client_id':client_id}