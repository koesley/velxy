"""HTTP contract checks for the VELXTRIA command surface.

Calls the actual GET handler with a response recorder, without opening a
port, requiring a customer session, or touching production credentials.
"""
import unittest


class ResponseRecorder:
    def __init__(self, path):
        self.path = path
        self.response = None

    def preview_guard(self):
        return False

    def respond(self, status, body, content_type='text/html; charset=utf-8', headers=()):
        self.response = (status, body, content_type, dict(headers))


class CommandSurfaceHTTPTests(unittest.TestCase):
    def request(self, path):
        from portal import Handler
        recorder = ResponseRecorder(path)
        Handler.do_GET(recorder)
        self.assertIsNotNone(recorder.response, f'No response for {path}')
        return recorder.response

    def test_command_palette_asset_serves_executable_javascript(self):
        status, body, mime, headers = self.request('/command-palette.js')
        self.assertEqual(status, 200)
        self.assertTrue(mime.startswith('application/javascript'))
        self.assertIn(b'dialog.showModal()', body)
        self.assertIn('must-revalidate', headers.get('Cache-Control', ''))

    def test_main_stylesheet_contains_command_surface_and_studio(self):
        status, body, mime, headers = self.request('/style.css')
        self.assertEqual(status, 200)
        self.assertTrue(mime.startswith('text/css'))
        self.assertIn(b'.vx-command-dialog', body)
        self.assertIn(b'.cmd-shell', body)
        self.assertIn(b'.studio-panel', body)
        self.assertIn('must-revalidate', headers.get('Cache-Control', ''))


if __name__ == '__main__':
    unittest.main()
