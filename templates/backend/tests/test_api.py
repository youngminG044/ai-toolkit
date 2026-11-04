from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend.app.main import create_app


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'app.sqlite3'
        self.client = self.enterContext(TestClient(create_app(self.path, static_dir=Path(self.temp.name) / 'missing')))

    def test_create_update_delete_and_pagination(self):
        created = self.client.post('/api/items', json={'title': '측정', 'value': 12}).json()
        self.assertEqual(self.client.get('/api/items').json()['total'], 1)
        response = self.client.put('/api/items/' + created['id'], json={'title': '확인', 'value': 13, 'status': 'done'})
        self.assertEqual(response.json()['status'], 'done')
        self.assertEqual(self.client.get('/api/items?limit=0').status_code, 422)
        self.assertEqual(self.client.delete('/api/items/' + created['id']).status_code, 204)
        self.assertEqual(self.client.delete('/api/items/' + created['id']).status_code, 404)

    def test_storage_survives_application_restart(self):
        self.client.post('/api/items', json={'title': 'persistent'})
        with TestClient(create_app(self.path)) as second:
            self.assertEqual(second.get('/api/items').json()['items'][0]['title'], 'persistent')

    def test_validation_and_parameterized_storage(self):
        self.assertEqual(self.client.post('/api/items', json={'title': '  '}).status_code, 422)
        self.assertEqual(self.client.post('/api/items', json={'title': 'x', 'status': 'invalid'}).status_code, 422)
        text = "x'); DROP TABLE items; --"
        self.client.post('/api/items', json={'title': text})
        self.assertEqual(self.client.get('/api/items').json()['items'][0]['title'], text)

    def test_csv_profile_and_error(self):
        result = self.client.post('/api/data/profile', json={'csv_text': 'team,value\nA,2\nA,4\n', 'group_by': 'team', 'value_column': 'value'})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()['groups'][0]['mean'], 3)
        self.assertEqual(self.client.post('/api/data/profile', json={'csv_text': 'a,b\n1\n'}).status_code, 422)

    def test_document_retrieval_citations_and_delete(self):
        empty = self.client.post('/api/rag/answer', json={'question': 'procedure'}).json()
        self.assertTrue(empty['abstained'])
        document = self.client.post('/api/documents', json={'name': 'manual.md', 'text': 'Alarm reset procedure: inspect the sensor first.'}).json()
        result = self.client.post('/api/rag/answer', json={'question': 'sensor procedure'}).json()
        self.assertFalse(result['abstained'])
        self.assertEqual(result['mode'], 'extractive')
        self.assertEqual(result['citations'][0]['source'], 'manual.md')
        self.assertEqual(self.client.get('/api/documents').json()[0]['name'], 'manual.md')
        self.assertEqual(self.client.delete('/api/documents/' + document['id']).status_code, 204)

    def test_unknown_citations_from_generator_are_rejected(self):
        def bad_generator(question, passages):
            return {'text': 'unsupported', 'citation_ids': ['not-retrieved']}
        with TestClient(create_app(Path(self.temp.name) / 'other.sqlite3', generator=bad_generator)) as client:
            client.post('/api/documents', json={'name': 'x', 'text': 'sensor manual'})
            self.assertEqual(client.post('/api/rag/answer', json={'question': 'sensor'}).status_code, 422)

    def test_health_and_openapi(self):
        self.assertEqual(self.client.get('/health').json(), {'status': 'ok'})
        self.assertEqual(self.client.get('/api/health').json()['status'], 'ok')
        schema = self.client.get('/openapi.json').json()
        self.assertIn('/api/rag/answer', schema['paths'])
        self.assertIn('requestBody', schema['paths']['/api/items']['post'])
        self.assertIn('404', schema['paths']['/api/items/{identifier}']['delete']['responses'])
        self.assertEqual(self.client.get('/docs').status_code, 200)
        self.assertEqual(self.client.get('/redoc').status_code, 200)

    def test_api_index_uses_actual_routes_and_escapes_descriptions(self):
        @self.client.app.get('/api/custom-status', summary='Custom <script>unsafe</script>')
        def custom_status():
            return {'status': 'custom'}

        response = self.client.get('/api')
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/html', response.headers['content-type'])
        self.assertIn('/api/custom-status', response.text)
        self.assertIn('&lt;script&gt;unsafe&lt;/script&gt;', response.text)
        self.assertNotIn('<script>unsafe</script>', response.text)
        self.assertIn('/api/rag/answer', response.text)
        self.assertIn('href="openapi.json"', response.text)

    def test_docs_can_be_disabled_without_disabling_api_or_health(self):
        directory = Path(self.temp.name) / 'static-private'
        directory.mkdir()
        (directory / 'index.html').write_text('<html>Application</html>')
        with patch.dict('os.environ', {'ENABLE_API_DOCS': 'false'}):
            with TestClient(create_app(self.path, static_dir=directory)) as client:
                for path in ['/api', '/docs', '/redoc', '/openapi.json']:
                    self.assertEqual(client.get(path).status_code, 404, path)
                self.assertEqual(client.get('/health').json(), {'status': 'ok'})
                self.assertEqual(client.get('/api/items').status_code, 200)
                self.assertIn('Application', client.get('/').text)
            with TestClient(create_app(self.path, enable_api_docs=True)) as client:
                self.assertEqual(client.get('/api').status_code, 200)

    def test_static_frontend_and_api_share_one_app(self):
        directory = Path(self.temp.name) / 'static'
        directory.mkdir()
        (directory / 'index.html').write_text('<html><body>Workspace</body></html>')
        with TestClient(create_app(self.path, static_dir=directory)) as client:
            self.assertIn('Workspace', client.get('/').text)
            self.assertEqual(client.get('/api/health').status_code, 200)
            self.assertEqual(client.get('/health').status_code, 200)
            self.assertIn('/api/items', client.get('/api').text)
            self.assertEqual(client.get('/api/nonexistent').status_code, 404)


if __name__ == '__main__':
    unittest.main()
