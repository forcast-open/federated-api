# Imports
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()



#### Database tables ####



# Database class
class ClientsData(db.Model):
	__tablename__ = 'clients_data'

	client_id     = db.Column(db.Integer, primary_key=True) # unique id identifier per client
	state         = db.Column(db.String,  nullable=False)
	weights       = db.Column(db.String,  nullable=False)
	data_len      = db.Column(db.Integer, nullable=False)
	com_round_id  = db.Column(db.String,  nullable=False)
	last_modified = db.Column(db.String,  nullable=False)

	def __repr__(self):
		return f'Client {self.client_id} in state {self.state}'

# Database class
class ServerData(db.Model):
	__tablename__ = 'server_data'

	server_id     = db.Column(db.Integer, primary_key=True) # unique id identifier per server
	state         = db.Column(db.String,  nullable=False)
	weights       = db.Column(db.String,  nullable=False)
	com_round_id  = db.Column(db.String,  nullable=False)
	last_modified = db.Column(db.String,  nullable=False)
	context       = db.Column(db.String,  nullable=True)
	
	def __repr__(self):
		return f'Server {self.server_id} in state {self.state}'