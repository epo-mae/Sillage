"""Verify credentials without printing them or provider response bodies."""
import json, os, sys
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from sillage.config import load_environment

load_environment()
key=os.environ.get('FRAGELLA_API_KEY','')
if not key:
    print('FRAGELLA_API_KEY is not configured.');sys.exit(1)
print('Public-widget key:',key.startswith('pub_'))
print('Whitespace in key:',any(c.isspace()for c in key))
request=Request('https://api.fragella.com/api/v1/fragrances?search=Sauvage&limit=1',headers={'x-api-key':key,'Accept':'application/json','User-Agent':'Sillage/0.2'})
try:
    with urlopen(request,timeout=8)as response:
        data=json.load(response)
        if isinstance(data,dict):data=data.get('data',[])
        print('API status:',response.status)
        print('Result count:',len(data))
except HTTPError as error:
    body=error.read(4096).decode('utf-8','replace').lower()
    print(dict(status=error.code,json_response='json'in error.headers.get('Content-Type',''),
               invalid_key='invalid'in body and 'key'in body,expired_key='expired'in body,
               quota='quota'in body,missing_key='missing'in body and 'key'in body,cloudflare='cloudflare'in body))
    sys.exit(1)
except (URLError,TimeoutError):
    print('The provider could not be reached.');sys.exit(1)
