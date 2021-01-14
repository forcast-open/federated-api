import os
from flask import Flask
from flask_restful import Api
from flask_sqlalchemy import SQLAlchemy
from celery import Celery
# Database imports
from utils.models import ClientsData, ServerData, db

#### App services configuration ####



postgres_user     = os.environ.get('POSTGRES_USER')
postgres_password = os.environ.get('POSTGRES_PASSWORD')
postgres_db       = os.environ.get('POSTGRES_DB')


# Initialize Flask to bind with database

app = Flask('server')
app.config.update(
	SQLALCHEMY_DATABASE_URI        = f'postgresql://{postgres_user}:{postgres_password}@db:5432/{postgres_db}',
	SQLALCHEMY_TRACK_MODIFICATIONS = False,
	result_backend                 = 'redis://redis:6379',
	broker_url                     = 'redis://redis:6379'
)



#### Celery configuration ####



def make_celery(app):
    celery = Celery(
        app.import_name,
        backend = app.config['result_backend'],
        broker  = app.config['broker_url']
    )
    celery.conf.update(app.config)

    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask
    return celery



celery  = make_celery(app)
api     = Api(app)
db.init_app(app)
app.app_context().push()
