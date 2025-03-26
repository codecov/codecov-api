import unittest
from datetime import datetime
import math

from api.gen_ai.math import (
    add, 
    subtract, 
    divide, 
    factorial, 
    is_prime, 
    fibonacci, 
    Calculator, 
    StringManipulator, 
    DataProcessor, 
    parse_date, 
    safe_list_access, 
    merge_dicts
)


class BasicArithmeticFunctionsTests(unittest.TestCase):
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


class FactorialTests(unittest.TestCase):
    def test_factorial(self):
        self.assertEqual(factorial(0), 1)
        self.assertEqual(factorial(1), 1)
        self.assertEqual(factorial(5), 120)
        self.assertEqual(factorial(10), 3628800)

    def test_factorial_negative(self):
        with self.assertRaises(ValueError) as context:
            factorial(-1)
        self.assertEqual(str(context.exception), "Negative numbers do not have factorials")


class PrimeTests(unittest.TestCase):
    def test_is_prime(self):
        self.assertFalse(is_prime(0))
        self.assertFalse(is_prime(1))
        self.assertTrue(is_prime(2))
        self.assertTrue(is_prime(3))
        self.assertFalse(is_prime(4))
        self.assertTrue(is_prime(5))
        self.assertFalse(is_prime(6))
        self.assertTrue(is_prime(7))
        self.assertFalse(is_prime(9))
        self.assertTrue(is_prime(11))
        self.assertTrue(is_prime(13))
        self.assertTrue(is_prime(17))
        self.assertTrue(is_prime(19))
        self.assertTrue(is_prime(23))
        self.assertTrue(is_prime(29))
        self.assertTrue(is_prime(31))
        self.assertFalse(is_prime(33))
        self.assertTrue(is_prime(97))
        self.assertFalse(is_prime(100))


class FibonacciTests(unittest.TestCase):
    def test_fibonacci(self):
        self.assertEqual(fibonacci(0), 0)
        self.assertEqual(fibonacci(1), 1)
        self.assertEqual(fibonacci(2), 1)
        self.assertEqual(fibonacci(3), 2)
        self.assertEqual(fibonacci(4), 3)
        self.assertEqual(fibonacci(5), 5)
        self.assertEqual(fibonacci(6), 8)
        self.assertEqual(fibonacci(10), 55)
        self.assertEqual(fibonacci(15), 610)

    def test_fibonacci_negative(self):
        with self.assertRaises(ValueError) as context:
            fibonacci(-1)
        self.assertEqual(str(context.exception), "n must be a non-negative integer")


class CalculatorTests(unittest.TestCase):
    def setUp(self):
        self.calculator = Calculator()

    def test_add(self):
        self.assertEqual(self.calculator.add(2, 3), 5)

    def test_subtract(self):
        self.assertEqual(self.calculator.subtract(5, 3), 2)

    def test_multiply(self):
        self.assertEqual(self.calculator.multiply(2, 3), 6)

    def test_divide(self):
        self.assertEqual(self.calculator.divide(6, 3), 2)

    def test_divide_by_zero(self):
        with self.assertRaises(ValueError) as context:
            self.calculator.divide(5, 0)
        self.assertEqual(str(context.exception), "Cannot divide by zero")

    def test_memory(self):
        self.calculator.store(10)
        self.assertEqual(self.calculator.recall(), 10)
        self.calculator.store(20)
        self.assertEqual(self.calculator.recall(), 20)


class StringManipulatorTests(unittest.TestCase):
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


class DataProcessorTests(unittest.TestCase):
    def test_get_mean(self):
        processor = DataProcessor([1, 2, 3, 4, 5])
        self.assertEqual(processor.get_mean(), 3)

    def test_get_variance(self):
        processor = DataProcessor([1, 2, 3, 4, 5])
        self.assertEqual(processor.get_variance(), 2.5)

    def test_normalize(self):
        processor = DataProcessor([1, 2, 3, 4, 5])
        normalized = processor.normalize()
        expected = [-1.265, -0.632, 0, 0.632, 1.265]
        # Compare rounded values due to floating point precision
        for i, val in enumerate(normalized):
            self.assertAlmostEqual(val, expected[i], places=3)

    def test_empty_data(self):
        with self.assertRaises(ValueError) as context:
            DataProcessor([])
        self.assertEqual(str(context.exception), "Data list cannot be empty")

    def test_single_value_variance(self):
        processor = DataProcessor([5])
        with self.assertRaises(ValueError) as context:
            processor.get_variance()
        self.assertEqual(str(context.exception), "At least two data points are required to compute variance")


class DateParserTests(unittest.TestCase):
    def test_parse_date(self):
        self.assertEqual(parse_date("2023-01-15"), datetime(2023, 1, 15))
        self.assertEqual(parse_date("2023-12-31"), datetime(2023, 12, 31))

    def test_parse_date_custom_format(self):
        self.assertEqual(parse_date("15/01/2023", fmt="%d/%m/%Y"), datetime(2023, 1, 15))

    def test_parse_date_invalid(self):
        with self.assertRaises(ValueError):
            parse_date("invalid-date")


class UtilityFunctionsTests(unittest.TestCase):
    def test_safe_list_access(self):
        my_list = [1, 2, 3]
        self.assertEqual(safe_list_access(my_list, 0), 1)
        self.assertEqual(safe_list_access(my_list, 2), 3)
        self.assertIsNone(safe_list_access(my_list, 3))
        self.assertEqual(safe_list_access(my_list, 3, default="not found"), "not found")
        self.assertEqual(safe_list_access([], 0, default="empty"), "empty")

    def test_merge_dicts(self):
        dict1 = {"a": 1, "b": 2}
        dict2 = {"b": 3, "c": 4}
        merged = merge_dicts(dict1, dict2)
        self.assertEqual(merged, {"a": 1, "b": 3, "c": 4})

        # Test recursive merging
        dict1 = {"a": 1, "b": {"x": 10, "y": 20}}
        dict2 = {"b": {"y": 30, "z": 40}, "c": 4}
        merged = merge_dicts(dict1, dict2)
        self.assertEqual(merged, {"a": 1, "b": {"x": 10, "y": 30, "z": 40}, "c": 4})

        # Test that original dicts are not modified
        self.assertEqual(dict1, {"a": 1, "b": {"x": 10, "y": 20}})
        self.assertEqual(dict2, {"b": {"y": 30, "z": 40}, "c": 4})