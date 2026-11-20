"""Regression tests for SQL-aware positional parameter translation."""
import unittest
from sql_params import translate_qmark

class SQLParameterTests(unittest.TestCase):
    def test_normal(self):
        self.assertEqual(
            translate_qmark('SELECT * FROM users WHERE id=? AND role=?'),
            'SELECT * FROM users WHERE id=%s AND role=%s'
        )

    def test_literals(self):
        self.assertEqual(
            translate_qmark("SELECT '?', 'it''s ?', \"col?\" WHERE id=?"),
            "SELECT '?', 'it''s ?', \"col?\" WHERE id=%s"
        )

    def test_comments(self):
        self.assertEqual(
            translate_qmark('SELECT ? -- ?\\n, ? /* ? */'.replace('\\n', '\n')),
            'SELECT %s -- ?\\n, %s /* ? */'.replace('\\n', '\n')
        )

    def test_nested_comments(self):
        self.assertEqual(
            translate_qmark('SELECT /* a /* ? */ ? */ ?'),
            'SELECT /* a /* ? */ ? */ %s'
        )

    def test_dollar_quoted_strings(self):
        self.assertEqual(
            translate_qmark('SELECT $$?$$, $tag$?$tag$, ?'),
            'SELECT $$?$$, $tag$?$tag$, %s'
        )

    def test_empty(self):
        self.assertEqual(translate_qmark(''), '')

    def test_invalid_input(self):
        with self.assertRaises(TypeError):
            translate_qmark(None)

if __name__ == '__main__':
    unittest.main()
