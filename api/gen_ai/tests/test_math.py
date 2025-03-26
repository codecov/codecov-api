import math
import unittest
from datetime import datetime

import pytest
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
        self.assertEqual(add(2, 3), 5)
        self.assertEqual(add(-1, 1), 0)
        self.assertEqual(add(0, 0), 0)
        self.assertEqual(add(2.5, 3.5), 6.0)

    def test_subtract(self):
        self.assertEqual(subtract(5, 3), 2)
        self.assertEqual(subtract(1, 1), 0)
        self.assertEqual(subtract(0, 5), -5)
        self.assertEqual(subtract(5.5, 2.5), 3.0)

    def test_divide(self):
        self.assertEqual(divide(6, 3), 2)
        self.assertEqual(divide(5, 2), 2.5)
        self.assertEqual(divide(0, 5), 0)
        self.assertEqual(divide(-6, 3), -2)

    def test_divide_by_zero(self):
        with self.assertRaises(ValueError) as context:
            divide(5, 0)
        self.assertEqual(str(context.exception), "Division by zero is not allowed")


class TestFactorial(unittest.TestCase):
    def test_factorial_positive(self):
        self.assertEqual(factorial(0), 1)
        self.assertEqual(factorial(1), 1)
        self.assertEqual(factorial(5), 120)
        self.assertEqual(factorial(10), 3628800)

    def test_factorial_negative(self):
        with self.assertRaises(ValueError) as context:
            factorial(-1)
        self.assertEqual(str(context.exception), "Negative numbers do not have factorials")


class TestIsPrime(unittest.TestCase):
    def test_is_prime(self):
        self.assertFalse(is_prime(0))
        self.assertFalse(is_prime(1))
        self.assertTrue(is_prime(2))
        self.assertTrue(is_prime(3))
        self.assertFalse(is_prime(4))
        self.assertTrue(is_prime(5))
        self.assertFalse(is_prime(6))
        self.assertTrue(is_prime(7))
        self.assertTrue(is_prime(11))
        self.assertTrue(is_prime(13))
        self.assertTrue(is_prime(17))
        self.assertTrue(is_prime(19))
        self.assertTrue(is_prime(97))
        self.assertFalse(is_prime(100))


class TestFibonacci(unittest.TestCase):
    def test_fibonacci(self):
        self.assertEqual(fibonacci(0), 0)
        self.assertEqual(fibonacci(1), 1)
        self.assertEqual(fibonacci(2), 1)
        self.assertEqual(fibonacci(3), 2)
        self.assertEqual(fibonacci(4), 3)
        self.assertEqual(fibonacci(5), 5)
        self.assertEqual(fibonacci(6), 8)
        self.assertEqual(fibonacci(10), 55)

    def test_fibonacci_negative(self):
        with self.assertRaises(ValueError) as context:
            fibonacci(-1)
        self.assertEqual(str(context.exception), "n must be a non-negative integer")


class TestCalculator(unittest.TestCase):
    def setUp(self):
        self.calc = Calculator()

    def test_add(self):
        self.assertEqual(self.calc.add(2, 3), 5)

    def test_subtract(self):
        self.assertEqual(self.calc.subtract(5, 3), 2)

    def test_multiply(self):
        self.assertEqual(self.calc.multiply(2, 3), 6)

    def test_divide(self):
        self.assertEqual(self.calc.divide(6, 3), 2)
        self.assertEqual(self.calc.divide(5, 2), 2.5)

    def test_divide_by_zero(self):
        with self.assertRaises(ValueError) as context:
            self.calc.divide(5, 0)
        self.assertEqual(str(context.exception), "Cannot divide by zero")

    def test_memory_operations(self):
        self.calc.store(5)
        self.assertEqual(self.calc.recall(), 5)
        self.calc.store(10)
        self.assertEqual(self.calc.recall(), 10)


class TestStringManipulator(unittest.TestCase):
    def test_reverse_string(self):
        self.assertEqual(StringManipulator.reverse_string("hello"), "olleh")
        self.assertEqual(StringManipulator.reverse_string(""), "")
        self.assertEqual(StringManipulator.reverse_string("a"), "a")
        self.assertEqual(StringManipulator.reverse_string("12345"), "54321")

    def test_is_palindrome(self):
        self.assertTrue(StringManipulator.is_palindrome("racecar"))
        self.assertTrue(StringManipulator.is_palindrome("A man, a plan, a canal: Panama"))
        self.assertTrue(StringManipulator.is_palindrome(""))
        self.assertTrue(StringManipulator.is_palindrome("a"))
        self.assertFalse(StringManipulator.is_palindrome("hello"))
        self.assertFalse(StringManipulator.is_palindrome("world"))


class TestDataProcessor(unittest.TestCase):
    def test_get_mean(self):
        dp = DataProcessor([1, 2, 3, 4, 5])
        self.assertEqual(dp.get_mean(), 3.0)

    def test_get_variance(self):
        dp = DataProcessor([1, 2, 3, 4, 5])
        self.assertEqual(dp.get_variance(), 2.5)

    def test_normalize(self):
        dp = DataProcessor([1, 2, 3, 4, 5])
        normalized = dp.normalize()
        expected = [
            -1.264911064067352,
            -0.6324555320336759,
            0.0,
            0.6324555320336759,
            1.264911064067352,
        ]
        for i in range(len(normalized)):
            self.assertAlmostEqual(normalized[i], expected[i])

    def test_empty_data(self):
        with self.assertRaises(ValueError) as context:
            dp = DataProcessor([])
        self.assertEqual(str(context.exception), "Data list cannot be empty")

    def test_variance_single_value(self):
        dp = DataProcessor([5])
        with self.assertRaises(ValueError) as context:
            dp.get_variance()
        self.assertEqual(str(context.exception), "At least two data points are required to compute variance")


class TestUtilityFunctions(unittest.TestCase):
    def test_parse_date(self):
        self.assertEqual(parse_date("2023-01-01"), datetime(2023, 1, 1))
        with self.assertRaises(ValueError):
            parse_date("01/01/2023")

    def test_safe_list_access(self):
        test_list = [1, 2, 3]
        self.assertEqual(safe_list_access(test_list, 1), 2)
        self.assertEqual(safe_list_access(test_list, 5), None)
        self.assertEqual(safe_list_access(test_list, 5, "default"), "default")

    def test_merge_dicts(self):
        dict1 = {"a": 1, "b": {"c": 2, "d": 3}}
        dict2 = {"b": {"e": 4}, "f": 5}
        result = merge_dicts(dict1, dict2)
        expected = {"a": 1, "b": {"c": 2, "d": 3, "e": 4}, "f": 5}
        self.assertEqual(result, expected)