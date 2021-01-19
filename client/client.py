import os
import sys
import requests
from sklearn.model_selection import train_test_split
import jsonpickle as jpk
import time
# Federated imports
import forcast_federated_learning as ffl

# Parameters
BASE = 'http://127.0.0.1:5000/'
SERVER_ID          = int( os.environ.get('SERVER_ID') )
num_clients        = int( os.environ.get('NUM_CLIENTS') )
com_rounds         = int( os.environ.get('COM_ROUNDS') )
classes_per_client = int( os.environ.get('CLASSES_PER_CLIENT') )
seed               = 0


# Load local train data
X, y, df_data, target_names = ffl.datasets.load_scikit_iris()
# Split the database in train and test
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.33, stratify=y, random_state=seed)  

# Create custom pytorch datasers for train and testing
traindata = ffl.datasets.StructuredDataset(X_train, y_train)
testdata  = ffl.datasets.StructuredDataset(X_test, y_test)

# Create federated model based on a pytorch model
model           = ffl.models.NN(input_dim=traindata.num_features, output_dim=traindata.num_classes) # pytorch model
local_model     = ffl.LocalModel(model, model_type='nn', local_optimizer = 'Adam', local_opt_params = {'lr': 0.01, 'batch_size':64, 'epochs':4},)
weights         = local_model.state_dict()

# Create client
data = {'client_id'   : None, 
		'weights'     : '', 
		'state'       : 'iddle',
		'com_round_id': '',
		'data_len'    : 1}
resp = requests.post(BASE + 'api/v1.0/clients/', data=data)
print('POST:', resp.json())
CLIENT_ID = resp.json()['client_id']

# Split the train data and use only a fraction
traindata_split = ffl.data.random_non_iid_split(traindata, n_clients=num_clients, classes_per_client=classes_per_client, seed=seed)
traindata       = traindata_split[CLIENT_ID - 1]


# Get data loader
batch_size   = local_model.local_opt_params['batch_size']
train_loader = ffl.utils.DataLoader(traindata, batch_size=batch_size, shuffle=True)
test_loader  = ffl.utils.DataLoader(testdata, batch_size=len(testdata), shuffle=True)
data_len     = len(train_loader.dataset)




#### Federated training loop ####



count       = 0
while count < com_rounds:
	time.sleep(0.5)
	#### Communication round ####

	# Ckeck for server state
	resp = requests.get(BASE + 'api/v1.0/server/', data={'server_id': SERVER_ID, 'return_keys': ['state', 'com_round_id']})
	server_state, server_com_id  = map(resp.json().get, ['state', 'com_round_id'])
	if server_state != 'waiting':
		continue

	# Ckeck for client state
	resp = requests.get(BASE + 'api/v1.0/clients/', data={'client_id': CLIENT_ID, 'return_keys': ['state', 'com_round_id']})
	if resp.status_code == 404: # Not found
		sys.exit()
	client_state, client_com_id  = map(resp.json().get, ['state', 'com_round_id'])

	# Check if correct comunication round
	if (server_com_id != client_com_id):
		# Check if client wants to join this comunication round
		pass

	# Check if ready to train
	if (client_state == 'iddle') and (server_com_id != client_com_id):
		#### Train locally ####

		# Get updated server model
		resp = requests.get(BASE + 'api/v1.0/server/', data={'server_id': SERVER_ID, 'return_keys': ['weights']})
		weights    = resp.json()['weights']
		state_dict = jpk.decode(weights)
		local_model.load_state_dict(state_dict)

		acc, _   = local_model.test(test_loader)
		loss     = local_model.train(train_loader)
		weights  = local_model.state_dict()
		print(f'Test accuracy: {acc}\tTrain loss: {loss}') 
		# Send updated model to server
		data   = {'client_id'   : CLIENT_ID, 
				  'weights'     : jpk.encode(weights), 
				  'state'       : 'updated',
				  'com_round_id': server_com_id,
				  'data_len'    : data_len}
		resp   = requests.put(BASE + 'api/v1.0/clients/', data=data)
		count += 1

print(f'Finished {com_rounds} iterations')

time.sleep(6)
# If finished comunication rounds. Restart clients database
resp = requests.post(BASE + 'api/v1.0/clear_table/', data={'table_name': 'clients_data', 'column': 'client_id'})
print(resp.json())
# Restart server weights
resp = requests.post(BASE + 'api/v1.0/reset/', data={'table_name': 'server_data', 'row_id': SERVER_ID})