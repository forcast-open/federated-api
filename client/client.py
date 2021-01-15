import os
import requests
from sklearn.model_selection import train_test_split
import jsonpickle as jpk
import time
# Federated imports
import forcast_federated_learning as ffl

# Parameters
BASE = 'http://127.0.0.1:5000/'
SERVER_ID = os.environ.get('SERVER_ID')
num_clients = 10
com_rounds  = 10



# Load local train data
X, y, df_data, target_names = ffl.datasets.load_scikit_iris()
# Split the database in train and test
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.33, stratify=y, random_state=0)  

# Create custom pytorch datasers for train and testing
traindata = ffl.datasets.StructuredDataset(X_train, y_train)
testdata  = ffl.datasets.StructuredDataset(X_test, y_test)

# Create federated model based on a pytorch model
model       = ffl.models.NN(input_dim=traindata.num_features, output_dim=traindata.num_classes) # pytorch model
local_model = ffl.LocalModel(model, model_type='nn')
weights     = local_model.state_dict()

# Create client
data = {'client_id'   : None, 
		'weights'     : '', 
		'state'       : 'iddle',
		'com_round_id': '',
		'data_len'    : 1}
resp = requests.post(BASE + 'api/v1.0/clients', data=data)
print('POST:', resp.json())
CLIENT_ID = resp.json()['client_id']

# Split the train data and use only a fraction
traindata_split = ffl.data.random_split(traindata, num_clients, seed=0)
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
	resp = requests.get(BASE + 'api/v1.0/server', data={'server_id': SERVER_ID, 'return_keys': ['state', 'com_round_id']})
	server_state, server_com_id  = map(resp.json().get, ['state', 'com_round_id'])
	if server_state != 'waiting':
		continue

	# Ckeck for client state
	resp = requests.get(BASE + 'api/v1.0/clients', data={'client_id': CLIENT_ID, 'return_keys': ['state', 'com_round_id']})
	client_state, client_com_id  = map(resp.json().get, ['state', 'com_round_id'])

	if (client_state != 'iddle') and (server_com_id == client_com_id):
		continue
		
	#### Else: Train locally ####

	# Get updated server model
	resp = requests.get(BASE + 'api/v1.0/server', data={'server_id': SERVER_ID, 'return_keys': ['weights']})
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
	resp   = requests.put(BASE + 'api/v1.0/clients', data=data)
	count += 1