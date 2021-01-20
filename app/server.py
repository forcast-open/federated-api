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
SERVER_ID = int( os.environ.get('SERVER_ID') )

# Initialize database
task = celery.send_task('tasks.database_init', args=(), kwargs={})



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
clients_post_args.add_argument('com_round_id', type=str, help='com_round_id can be None an UUID string'             , required=False)

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
		client    = ClientsData(client_id=data['client_id'], state=data['state'], weights=data['weights'], data_len=data['data_len'], com_round_id=data['com_round_id'], last_modified = datetime.utcnow())
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

	def delete(self):
		data      = clients_get_args.parse_args()
		client_id = data['client_id']
		keys      = data['return_keys']
		result    = ClientsData.query.filter_by(client_id=client_id).first()
		if not result: # if client not found (result == None) return error
			abort(404, message=f'Could not find client with id {client_id}')
		output_dict = {}
		if keys: # if keys are specified return only that elements of the client information 
			output_dict = marshal(result, client_resource_fields)
			output_dict = {**{'client_id':client_id}, **dict(zip(keys, map(output_dict.get, keys)))} # join the two dictionaries
		db.session.delete(result)
		db.session.commit()

		return {**{'message':f'Removal of client {client_id} weights successful', 'client_id':client_id}, **output_dict}, 200



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

	def delete(self):
		data      = server_get_args.parse_args()
		server_id = data['server_id']
		keys      = data['return_keys']
		result    = ServerData.query.filter_by(server_id=server_id).first()
		if not result: # if server not found (result == None) return error
			abort(404, message=f'Could not find server with id {server_id}')
		output_dict = {}
		if keys: # if keys are specified return only that elements of the server information 
			output_dict = marshal(result, server_resource_fields)
			output_dict = {**{'server_id':server_id}, **dict(zip(keys, map(output_dict.get, keys)))} # join the two dictionaries
		db.session.delete(result)
		db.session.commit()

		return {**{'message':f'Removal of server {server_id} weights successful', 'server_id':server_id}, **output_dict}, 200



#### Clear ####



# Request parser
clear_parser = reqparse.RequestParser()
clear_parser.add_argument('table_name', type=str, help='table_name is required', required=True)
clear_parser.add_argument('column'    , type=str, help='column is required'    , required=True)

# Resource: flask api
class Clear_Table(Resource):
	def post(self):
		data       = clear_parser.parse_args()
		table_name = data['table_name']
		column     = data['column']
		# Delete all entries of the clients database
		db.engine.execute(f'DELETE FROM {table_name}')
		# Reset autoincrement value of database to zero, to run easily another simulation
		db.engine.execute(f'ALTER SEQUENCE {table_name}_{column}_seq RESTART WITH 1')
		# Commit changes to database
		db.session.commit()

		return {'message': f'Table {table_name} cleared successfully.'}




#### Reset ####



# Request parser
reset_parser = reqparse.RequestParser()
reset_parser.add_argument('table_name', type=str, help='table_name is required'                     , required=True)
reset_parser.add_argument('row_id'    , type=str, help='row_id is required (client_id or server_id)', required=True)


# Resource: flask api
class Reset(Resource):
	def post(self):
		data       = reset_parser.parse_args()
		table_name = data['table_name']
		if table_name == 'server_data':
			server_id = data['row_id']
			task = celery.send_task('tasks.reset_server_weights', args=(), kwargs={'server_id': server_id})

			return {'message': 'Reseting server weights', 'server_id': server_id, 'task_id': task.id}
		elif table_name == 'clients_data':
			client_id = data['row_id']
			task = celery.send_task('tasks.reset_client_weights', args=(), kwargs={'client_id': client_id})

			return {'message': 'Reseting client weights', 'client_id': client_id, 'task_id': task.id}
		else:
			return {'message': 'Only server_data and clients_data suported as table_name.'}




#### Endpoints ####



# Index
@app.route('/')
def index():
	return {'message': 'FFL: Simple API with Restful'}

# Define and add resources
api.add_resource(Clients,     '/api/v1.0/clients/')
api.add_resource(Server,      '/api/v1.0/server/')
api.add_resource(Clear_Table, '/api/v1.0/clear_table/')
api.add_resource(Reset,       '/api/v1.0/reset/')

# Run app
if __name__ == '__main__':
	app.run(host='0.0.0.0', port=5000, debug=False)