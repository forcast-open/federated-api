import os
from flask import Flask, request, jsonify
from flask_restful import Resource, Api, reqparse, abort, marshal, fields
from flask_migrate import Migrate, MigrateCommand
from flask_sqlalchemy import SQLAlchemy
from flask_script import Manager
import jsonpickle as jspk
# Api imports
# from worker import celery, app, api, db
from datetime import datetime
import celery.states as states
# Database imports
from utils.models import ClientsData, ServerData
from utils.worker import app, api, celery, db

# Parameters
SERVER_ID = os.environ.get('SERVER_ID')

# Initialize database
task = celery.send_task('tasks.database_init', args=[], kwargs={})



#### Client ####



# Request parsers

clients_get_args = reqparse.RequestParser()
clients_get_args.add_argument('client_id'  , type=int, help='client_id is required'                            , required=True)
clients_get_args.add_argument('return_keys', type=str, help='return only the specified keys of the client data', required=False, action='append')

clients_post_args = reqparse.RequestParser()
clients_post_args.add_argument('client_id'   , type=int, help='client_id can be None or int'                        , required=False)
clients_post_args.add_argument('weights'     , type=str, help='json pickled dictionary of model weights is required', required=True)
clients_post_args.add_argument('state'       , type=str, help='state is required'                                   , required=True)
clients_post_args.add_argument('data_len'    , type=int, help='data_len is required'                                , required=True)
clients_post_args.add_argument('com_round_id', type=str, help='com_round_id is required'                            , required=False)

# Resource fields for marshal serializer 
client_resource_fields = {
	'client_id'    : fields.Integer,
	'state'        : fields.String,
	'weights'      : fields.String,
	'data_len'     : fields.Integer,
	'com_round_id' : fields.String,
	'last_modified': fields.String,
}

# Resource: flask api
class Clients(Resource):
	def get(self):
		data      = clients_get_args.parse_args()
		client_id = data['client_id']
		keys      = data['return_keys']
		result    = ClientsData.query.filter_by(client_id=client_id).first()
		if not result: # if client not found (result == None) return error
			abort(404, message=f'Could not find client with id {client_id}')
		output_dict = marshal(result, client_resource_fields)
		if keys: # if keys are specified return only that elements of the client information 
			return {**{'client_id':client_id}, **dict(zip(keys, map(output_dict.get, keys)))} # join the two dictionaries
		else: 
			return output_dict

	def post(self):
		data      = clients_post_args.parse_args()
		client_id = data['client_id']
		result    = ClientsData.query.filter_by(client_id=client_id).first()
		if result: # if client already exists (result != None) return error
			abort(409, message=f'Client id {client_id} is taken...')
		client = ClientsData(client_id=data['client_id'], state=data['state'], weights=data['weights'], data_len=data['data_len'], com_round_id=data['com_round_id'], last_modified = datetime.utcnow())
		db.session.add(client)
		db.session.commit()
		client_id = client.client_id
		
		return {'message':f'Creation of client {client_id} weights successful', 'client_id':client_id}, 201

	def put(self):
		data      = clients_post_args.parse_args() # same args as post
		client_id = data['client_id']
		result    = ClientsData.query.filter_by(client_id=client_id).first()
		if not result: # if client not found (result == None) return error
			abort(404, message=f'Could not find client with id {client_id}, cannot update')
		result.client_id     = data['client_id']
		result.weights       = data['weights']
		result.state         = data['state']
		result.data_len      = data['data_len']
		result.com_round_id  = data['com_round_id']
		result.last_modified = datetime.utcnow()
		db.session.commit()
				
		return {'message':f'Update of client {client_id} weights successful', 'client_id':client_id}, 202



#### Server ####



# Request parsers

server_get_args = reqparse.RequestParser()
server_get_args.add_argument('server_id'  , type=int, help='server_id is required'                            , required=True)
server_get_args.add_argument('return_keys', type=str, help='return only the specified keys of the server data', action='append')

server_post_args = reqparse.RequestParser()
server_post_args.add_argument('server_id'   , type=int, help='server_id is required'                               , required=True)
server_post_args.add_argument('weights'     , type=str, help='json pickled dictionary of model weights is required', required=True)
server_post_args.add_argument('state'       , type=str, help='state is required'                                   , required=True)
server_post_args.add_argument('com_round_id', type=str, help='com_round_id is required'                            , required=True)


# Resource fields for marshal serializer 
server_resource_fields = {
	'server_id'   : fields.Integer,
	'state'       : fields.String,
	'weights'     : fields.String,
	'com_round_id': fields.String
}

# Resource: flask api
class Server(Resource):
	def get(self):
		data      = server_get_args.parse_args()
		server_id = data['server_id']
		keys      = data['return_keys']
		result    = ServerData.query.filter_by(server_id=server_id).first()
		if not result: # if server not found (result == None) return error
			abort(404, message=f'Could not find server with id {server_id}')
		output_dict = marshal(result, server_resource_fields)
		if keys: # if keys are specified return only that elements of the server information 
			return {**{'server_id':server_id}, **dict(zip(keys, map(output_dict.get, keys)))} # join the two dictionaries
		else: 
			return output_dict

	def post(self):
		data      = server_post_args.parse_args()
		server_id = data['server_id']
		result    = ServerData.query.filter_by(server_id=server_id).first()
		if result: # if server already exists (result != None) return error
			abort(409, message=f'Server id {server_id} is taken...')
		server = ServerData(server_id=data['server_id'], state=data['state'], weights=data['weights'], com_round_id=data['com_round_id'], last_modified = datetime.utcnow())
		db.session.add(server)
		db.session.commit()
		
		return {'message':f'Creation of server {server_id} weights successful', 'server_id':server_id}, 201

	def put(self):
		data      = server_post_args.parse_args() # same args as post
		server_id = data['server_id']
		result    = ServerData.query.filter_by(server_id=server_id).first()
		if not result: # if server not found (result == None) return error
			abort(404, message=f'Could not find server with id {server_id}, cannot update')
		result.server_id     = data['server_id']
		result.weights       = data['weights']
		result.state         = data['state']
		result.com_round_id  = data['com_round_id']
		result.last_modified = datetime.utcnow()
		db.session.commit()

		return {'message':f'Update of server {server_id} weights successful', 'server_id':server_id}, 202



#### Endpoints ####



# Index
@app.route('/')
def index():
	return {'message': 'FFL: Simple API with Restful'}

# Define and add resources
api.add_resource(Clients, '/api/v1.0/clients')
api.add_resource(Server,  '/api/v1.0/server')

# Run app
if __name__ == '__main__':
	app.run(host='0.0.0.0', port=5000, debug=False)