from contextlib import closing
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from sillage.app import create_app


class OwnerSetupTests(unittest.TestCase):
    def test_concurrent_setup_has_exactly_one_winner(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent.parent/'data') as folder:
            path=Path(folder)/'owner.db'
            app=create_app(path,testing=True)
            clients=[app.test_client(),app.test_client()]
            tokens=[client.get('/api/session').json['csrf'] for client in clients]
            self.assertTrue(clients[0].get('/api/session').json['registration_open'])
            def register(i):
                return clients[i].post('/api/auth/register',json=dict(name='Owner',email=f'owner{i}@example.com',password='owner-password'),headers={'X-CSRF-Token':tokens[i]}).status_code
            with ThreadPoolExecutor(max_workers=2) as executor:
                results=list(executor.map(register,range(2)))
            self.assertEqual(sorted(results),[200,403])
            with closing(sqlite3.connect(path)) as connection:
                self.assertEqual(connection.execute('SELECT COUNT(*) FROM users').fetchone()[0],1)

    def test_existing_multi_account_database_keeps_data_but_only_owner_can_sign_in(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent.parent/'data') as folder:
            path=Path(folder)/'legacy.db'
            app=create_app(path,testing=True)
            client=app.test_client()
            token=client.get('/api/session').json['csrf']
            client.post('/api/auth/register',json=dict(name='Owner',email='owner@example.com',password='owner-password'),headers={'X-CSRF-Token':token})
            with closing(sqlite3.connect(path)) as connection:
                connection.execute('DROP TRIGGER single_owner_registration')
                connection.execute("INSERT INTO users(email,name,password,preferences,created_at) SELECT 'other@example.com','Other',password,preferences,created_at FROM users LIMIT 1")
                connection.commit()
            client=create_app(path,testing=True).test_client()
            token=client.get('/api/session').json['csrf']
            response=client.post('/api/auth/login',json=dict(email='other@example.com',password='owner-password'),headers={'X-CSRF-Token':token})
            self.assertEqual(response.status_code,400)
            with client.session_transaction() as session:
                session['user_id']=2
            self.assertIsNone(client.get('/api/session').json['user'])
            self.assertEqual(client.get('/api/collection').status_code,401)
            with closing(sqlite3.connect(path)) as connection:
                self.assertEqual(connection.execute('SELECT COUNT(*) FROM users').fetchone()[0],2)
