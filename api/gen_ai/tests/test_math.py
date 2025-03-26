import unittest
from datetime import datetime
from unittest import TestCase

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


class BasicArithmeticTests(TestCase):
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


class FactorialTests(TestCase):
    def test_factorial_zero(self):
        self.assertEqual(factorial(0), 1)

    def test_factorial_one(self):
        self.assertEqual(factorial(1), 1)

    def test_factorial_positive(self):
        self.assertEqual(factorial(5), 120)
        self.assertEqual(factorial(10), 3628800)

    def test_factorial_negative(self):
        with self.assertRaises(ValueError) as context:
            factorial(-1)
        self.assertEqual(str(context.exception), "Negative numbers do not have factorials")


class PrimeTests(TestCase):
    def test_is_prime_negative_and_zero(self):
        self.assertFalse(is_prime(-5))
        self.assertFalse(is_prime(0))

    def test_is_prime_one(self):
        self.assertFalse(is_prime(1))

    def test_is_prime_two_and_three(self):
        self.assertTrue(is_prime(2))
        self.assertTrue(is_prime(3))

    def test_is_prime_regular_cases(self):
        self.assertTrue(is_prime(5))
        self.assertTrue(is_prime(7))
        self.assertTrue(is_prime(11))
        self.assertTrue(is_prime(13))
        self.assertTrue(is_prime(17))
        self.assertTrue(is_prime(19))
        self.assertTrue(is_prime(23))
        
        self.assertFalse(is_prime(4))
        self.assertFalse(is_prime(6))
        self.assertFalse(is_prime(8))
        self.assertFalse(is_prime(9))
        self.assertFalse(is_prime(10))

    def test_is_prime_larger_numbers(self):
        self.assertTrue(is_prime(97))
        self.assertFalse(is_prime(100))


class FibonacciTests(TestCase):
    def test_fibonacci_zero(self):
        self.assertEqual(fibonacci(0), 0)

    def test_fibonacci_one(self):
        self.assertEqual(fibonacci(1), 1)

    def test_fibonacci_sequence(self):
        expected_sequence = [0, 1, 1, 2, 3, 5, 8, 13, 21, 34]
        for n, expected in enumerate(expected_sequence):
            self.assertEqual(fibonacci(n), expected)

    def test_fibonacci_negative(self):
        with self.assertRaises(ValueError) as context:
            fibonacci(-1)
        self.assertEqual(str(context.exception), "n must be a non-negative integer")


class CalculatorTests(TestCase):
    def setUp(self):
        self.calculator = Calculator()

    def test_add(self):
        self.assertEqual(self.calculator.add(2, 3), 5)
        self.assertEqual(self.calculator.add(-1, 1), 0)

    def test_subtract(self):
        self.assertEqual(self.calculator.subtract(5, 3), 2)
        self.assertEqual(self.calculator.subtract(1, 1), 0)

    def test_multiply(self):
        self.assertEqual(self.calculator.multiply(2, 3), 6)
        self.assertEqual(self.calculator.multiply(5, 0), 0)

    def test_divide(self):
        self.assertEqual(self.calculator.divide(6, 3), 2)
        self.assertEqual(self.calculator.divide(5, 2), 2.5)

    def test_divide_by_zero(self):
        with self.assertRaises(ValueError) as context:
            self.calculator.divide(5, 0)
        self.assertEqual(str(context.exception), "Cannot divide by zero")

    def test_memory_operations(self):
        # Initial memory is 0
        self.assertEqual(self.calculator.memory, 0)
        
        # Store value
        self.calculator.store(42)
        self.assertEqual(self.calculator.memory, 42)
        
        # Recall value
        self.assertEqual(self.calculator.recall(), 42)
        
        # Store new value
        self.calculator.store(-10)
        self.assertEqual(self.calculator.recall(), -10)


class StringManipulatorTests(TestCase):
    def test_reverse_string(self):
        self.assertEqual(StringManipulator.reverse_string("hello"), "olleh")
        self.assertEqual(StringManipulator.reverse_string(""), "")
        self.assertEqual(StringManipulator.reverse_string("a"), "a")
        self.assertEqual(StringManipulator.reverse_string("12345"), "54321")

    def test_is_palindrome(self):
        # Simple cases
        self.assertTrue(StringManipulator.is_palindrome("racecar"))
        self.assertTrue(StringManipulator.is_palindrome("madam"))
        self.assertTrue(StringManipulator.is_palindrome(""))
        self.assertTrue(StringManipulator.is_palindrome("a"))
        self.assertFalse(StringManipulator.is_palindrome("hello"))
        
        # Case insensitivity
        self.assertTrue(StringManipulator.is_palindrome("Madam"))
        self.assertTrue(StringManipulator.is_palindrome("RaceCar"))
        
        # Ignoring non-alphanumeric characters
        self.assertTrue(StringManipulator.is_palindrome("A man, a plan, a canal: Panama"))
        self.assertTrue(StringManipulator.is_palindrome("No 'x' in Nixon"))


class DataProcessorTests(TestCase):
    def test_constructor_empty_data(self):
        with self.assertRaises(ValueError) as context:
            DataProcessor([])
        self.assertEqual(str(context.exception), "Data list cannot be empty")

    def test_get_mean(self):
        processor = DataProcessor([1, 2, 3, 4, 5])
        self.assertEqual(processor.get_mean(), 3)

        processor = DataProcessor([0, 0, 0])
        self.assertEqual(processor.get_mean(), 0)

        processor = DataProcessor([1.5, 2.5, 3.5])
        self.assertEqual(processor.get_mean(), 2.5)

    def test_get_variance(self):
        processor = DataProcessor([1, 2, 3, 4, 5])
        self.assertEqual(processor.get_variance(), 2.5)

        processor = DataProcessor([0, 0, 0])
        self.assertEqual(processor.get_variance(), 0)

    def test_get_variance_single_element(self):
        processor = DataProcessor([42])
        with self.assertRaises(ValueError) as context:
            processor.get_variance()
        self.assertEqual(str(context.exception), "At least two data points are required to compute variance")

    def test_normalize(self):
        processor = DataProcessor([1, 2, 3, 4, 5])
        expected = [-1.2649110640673518, -0.6324555320336759, 0, 0.6324555320336759, 1.2649110640673518]
        normalized = processor.normalize()
        self.assertEqual(len(normalized), 5)
        for actual, expected_value in zip(normalized, expected):
            self.assertAlmostEqual(actual, expected_value)

    def test_normalize_zero_std_dev(self):
        processor = DataProcessor([2, 2, 2])
        with self.assertRaises(ValueError) as context:
            processor.normalize()
        self.assertEqual(str(context.exception), "Standard deviation is zero, cannot normalize.")


class DateParsingTests(TestCase):
    def test_parse_date_default_format(self):
        date = parse_date("2023-01-15")
        self.assertEqual(date.year, 2023)
        self.assertEqual(date.month, 1)
        self.assertEqual(date.day, 15)

    def test_parse_date_custom_format(self):
        date = parse_date("15/01/2023", fmt="%d/%m/%Y")
        self.assertEqual(date.year, 2023)
        self.assertEqual(date.month, 1)
        self.assertEqual(date.day, 15)

    def test_parse_date_invalid_format(self):
        with self.assertRaises(ValueError) as context:
            parse_date("15-01-2023")
        self.assertEqual(str(context.exception), "Incorrect date format, should be YYYY-MM-DD")


class SafeListAccessTests(TestCase):
    def test_safe_list_access_valid_index(self):
        lst = [10, 20, 30, 40, 50]
        self.assertEqual(safe_list_access(lst, 2), 30)

    def test_safe_list_access_invalid_index(self):
        lst = [10, 20, 30]
        self.assertIsNone(safe_list_access(lst, 10))

    def test_safe_list_access_custom_default(self):
        lst = [10, 20, 30]
        self.assertEqual(safe_list_access(lst, 10, default="Not found"), "Not found")


class MergeDictsTests(TestCase):
    def test_merge_dicts_simple(self):
        dict1 = {"a": 1, "b": 2}
        dict2 = {"c": 3, "d": 4}
        result = merge_dicts(dict1, dict2)
        self.assertEqual(result, {"a": 1, "b": 2, "c": 3, "d": 4})

    def test_merge_dicts_with_overlap(self):
        dict1 = {"a": 1, "b": 2}
        dict2 = {"b": 3, "c": 4}
        result = merge_dicts(dict1, dict2)
        self.assertEqual(result, {"a": 1, "b": 3, "c": 4})

    def test_merge_dicts_nested(self):
        dict1 = {"a": 1, "b": {"x": 1, "y": 2}}
        dict2 = {"b": {"y": 3, "z": 4}, "c": 5}
        result = merge_dicts(dict1, dict2)
        self.assertEqual(result, {"a": 1, "b": {"x": 1, "y": 3, "z": 4}, "c": 5})

    def test_original_dicts_unchanged(self):
        dict1 = {"a": 1, "b": 2}
        dict2 = {"c": 3, "d": 4}
        original_dict1 = dict1.copy()
        original_dict2 = dict2.copy()
        
        merge_dicts(dict1, dict2)
        
        self.assertEqual(dict1, original_dict1)
        self.assertEqual(dict2, original_dict2)