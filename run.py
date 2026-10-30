import os
from waitress import serve
from sillage.app import create_app
from sillage.config import load_environment

if __name__=='__main__':
    load_environment()
    host=os.environ.get('SILLAGE_HOST','127.0.0.1')
    port=int(os.environ.get('SILLAGE_PORT','8000'))
    print(f'Sillage is available at http://{host}:{port}',flush=True)
    serve(create_app(os.environ.get('SILLAGE_DATABASE')),host=host,port=port,threads=6)
