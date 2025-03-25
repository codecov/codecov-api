import unittest
import math
from datetime import datetime
from api.gen_ai.math import (
    add, subtract, divide, factorial, is_prime, fibonacci,
    Calculator, StringManipulator, DataProcessor,
    parse_date, safe_list_access, merge_dicts
)


class BasicMathFunctionsTest(unittest.TestCase):
    def test_add(self):
        self.assertEqual(add(3, 5), 8)
        self.assertEqual(add(-1, 1), 0)
        self.assertEqual(add(0, 0), 0)
        self.assertEqual(add(3.5, 2.5), 6.0)

    def test_subtract(self):
        self.assertEqual(subtract(10, 5), 5)
        self.assertEqual(subtract(5, 10), -5)
        self.assertEqual(subtract(0, 0), 0)
        self.assertEqual(subtract(3.5, 2.5), 1.0)

    def test_divide(self):
        self.assertEqual(divide(10, 2), 5)
        self.assertEqual(divide(5, 2), 2.5)
        self.assertEqual(divide(0, 5), 0)
        self.assertAlmostEqual(divide(1, 3), 0.3333333333333333)

    def test_divide_by_zero(self):
        with self.assertRaises(ValueError) as context:
            divide(5, 0)
        self.assertEqual(str(context.exception), "Division by zero is not allowed")


class FactorialTest(unittest.TestCase):
    def test_factorial_zero(self):
        self.assertEqual(factorial(0), 1)

    def test_factorial_positive(self):
        self.assertEqual(factorial(1), 1)
        self.assertEqual(factorial(2), 2)
        self.assertEqual(factorial(3), 6)
        self.assertEqual(factorial(5), 120)
        self.assertEqual(factorial(10), 3628800)

    def test_factorial_negative(self):
        with self.assertRaises(ValueError) as context:
            factorial(-1)
        self.assertEqual(str(context.exception), "Negative numbers do not have factorials")


class PrimeTest(unittest.TestCase):
    def test_is_prime_negative_and_zero(self):
        self.assertFalse(is_prime(-5))
        self.assertFalse(is_prime(0))
        self.assertFalse(is_prime(1))

    def test_is_prime_small_primes(self):
        self.assertTrue(is_prime(2))
        self.assertTrue(is_prime(3))
        self.assertTrue(is_prime(5))
        self.assertTrue(is_prime(7))
        self.assertTrue(is_prime(11))
        self.assertTrue(is_prime(13))

    def test_is_prime_non_primes(self):
        self.assertFalse(is_prime(4))
        self.assertFalse(is_prime(6))
        self.assertFalse(is_prime(8))
        self.assertFalse(is_prime(9))
        self.assertFalse(is_prime(10))
        self.assertFalse(is_prime(12))

    def test_is_prime_larger_numbers(self):
        self.assertTrue(is_prime(17))
        self.assertTrue(is_prime(19))
        self.assertTrue(is_prime(23))
        self.assertFalse(is_prime(25))
        self.assertFalse(is_prime(100))
        self.assertTrue(is_prime(101))


class FibonacciTest(unittest.TestCase):
    def test_fibonacci_base_cases(self):
        self.assertEqual(fibonacci(0), 0)
        self.assertEqual(fibonacci(1), 1)

    def test_fibonacci_sequence(self):
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


class CalculatorTest(unittest.TestCase):
    def setUp(self):
        self.calc = Calculator()

    def test_calculator_add(self):
        self.assertEqual(self.calc.add(3, 5), 8)
        self.assertEqual(self.calc.add(-1, 1), 0)

    def test_calculator_subtract(self):
        self.assertEqual(self.calc.subtract(10, 5), 5)
        self.assertEqual(self.calc.subtract(5, 10), -5)

    def test_calculator_multiply(self):
        self.assertEqual(self.calc.multiply(3, 5), 15)
        self.assertEqual(self.calc.multiply(-2, 3), -6)
        self.assertEqual(self.calc.multiply(0, 5), 0)

    def test_calculator_divide(self):
        self.assertEqual(self.calc.divide(10, 2), 5)
        self.assertEqual(self.calc.divide(5, 2), 2.5)

    def test_calculator_divide_by_zero(self):
        with self.assertRaises(ValueError) as context:
            self.calc.divide(5, 0)
        self.assertEqual(str(context.exception), "Cannot divide by zero")

    def test_calculator_memory(self):
        self.assertEqual(self.calc.memory, 0)  # Default value
        self.calc.store(10)
        self.assertEqual(self.calc.memory, 10)
        self.assertEqual(self.calc.recall(), 10)
        self.calc.store(-5)
        self.assertEqual(self.calc.recall(), -5)


class StringManipulatorTest(unittest.TestCase):
    def test_reverse_string(self):
        self.assertEqual(StringManipulator.reverse_string("hello"), "olleh")
        self.assertEqual(StringManipulator.reverse_string(""), "")
        self.assertEqual(StringManipulator.reverse_string("a"), "a")
        self.assertEqual(StringManipulator.reverse_string("12345"), "54321")

    def test_is_palindrome(self):
        self.assertTrue(StringManipulator.is_palindrome("racecar"))
        self.assertTrue(StringManipulator.is_palindrome("A man a plan a canal Panama"))
        self.assertTrue(StringManipulator.is_palindrome(""))
        self.assertTrue(StringManipulator.is_palindrome("a"))
        self.assertFalse(StringManipulator.is_palindrome("hello"))
        self.assertFalse(StringManipulator.is_palindrome("world"))


class DataProcessorTest(unittest.TestCase):
    def test_data_processor_initialization(self):
        dp = DataProcessor([1, 2, 3, 4, 5])
        self.assertEqual(dp.data, [1, 2, 3, 4, 5])

    def test_data_processor_empty_data(self):
        with self.assertRaises(ValueError) as context:
            DataProcessor([])
        self.assertEqual(str(context.exception), "Data list cannot be empty")

    def test_get_mean(self):
        dp = DataProcessor([1, 2, 3, 4, 5])
        self.assertEqual(dp.get_mean(), 3)

        dp = DataProcessor([0, 10])
        self.assertEqual(dp.get_mean(), 5)

    def test_get_variance(self):
        dp = DataProcessor([1, 2, 3, 4, 5])
        self.assertEqual(dp.get_variance(), 2.5)

        dp = DataProcessor([2, 2, 2, 2])
        self.assertEqual(dp.get_variance(), 0)

    def test_get_variance_single_value(self):
        dp = DataProcessor([5])
        with self.assertRaises(ValueError) as context:
            dp.get_variance()
        self.assertEqual(str(context.exception), "At least two data points are required to compute variance")

    def test_normalize(self):
        dp = DataProcessor([1, 2, 3, 4, 5])
        normalized = dp.normalize()
        self.assertAlmostEqual(normalized[0], -1.2649110640673518)
        self.assertAlmostEqual(normalized[1], -0.6324555320336759)
        self.assertAlmostEqual(normalized[2], 0.0)
        self.assertAlmostEqual(normalized[3], 0.6324555320336759)
        self.assertAlmostEqual(normalized[4], 1.2649110640673518)

    def test_normalize_zero_variance(self):
        dp = DataProcessor([2, 2, 2, 2])
        with self.assertRaises(ValueError) as context:
            dp.normalize()
        self.assertEqual(str(context.exception), "Standard deviation is zero, cannot normalize.")


class UtilityFunctionsTest(unittest.TestCase):
    def test_parse_date_default_format(self):
        date = parse_date("2023-01-15")
        self.assertEqual(date, datetime(2023, 1, 15))

    def test_parse_date_custom_format(self):
        date = parse_date("15/01/2023", fmt="%d/%m/%Y")
        self.assertEqual(date, datetime(2023, 1, 15))

    def test_parse_date_invalid_format(self):
        with self.assertRaises(ValueError) as context:
            parse_date("invalid-date")
        self.assertEqual(str(context.exception), "Incorrect date format, should be YYYY-MM-DD")

    def test_safe_list_access(self):
        test_list = [1, 2, 3]
        self.assertEqual(safe_list_access(test_list, 0), 1)
        self.assertEqual(safe_list_access(test_list, 2), 3)
        self.assertIsNone(safe_list_access(test_list, 5))
        self.assertEqual(safe_list_access(test_list, 5, "default"), "default")

    def test_merge_dicts(self):
        dict1 = {"a": 1, "b": 2, "c": {"x": 1, "y": 2}}
        dict2 = {"b": 3, "d": 4, "c": {"y": 3, "z": 4}}
        merged = merge_dicts(dict1, dict2)
        self.assertEqual(merged, {"a": 1, "b": 3, "c": {"x": 1, "y": 3, "z": 4}, "d": 4})