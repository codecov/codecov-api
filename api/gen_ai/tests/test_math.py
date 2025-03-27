import unittest
from datetime import datetime
from unittest.mock import patch

from api.gen_ai.math import (
    Calculator,
    DataProcessor,
    StringManipulator,
    add,
    divide,
    factorial,
    fibonacci,
    is_prime,
    merge_dicts,
    parse_date,
    safe_list_access,
    subtract,
)


class TestBasicArithmeticFunctions(unittest.TestCase):
    def test_add(self):
        self.assertEqual(add(5, 3), 8)
        self.assertEqual(add(-1, 1), 0)
        self.assertEqual(add(0, 0), 0)
        self.assertEqual(add(5.5, 4.5), 10.0)
