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

    def test_subtract(self):
        self.assertEqual(subtract(5, 3), 2)
        self.assertEqual(subtract(-1, 1), -2)
        self.assertEqual(subtract(0, 0), 0)
        self.assertEqual(subtract(5.5, 4.5), 1.0)

    def test_divide(self):
        self.assertEqual(divide(6, 3), 2)
        self.assertEqual(divide(5, 2), 2.5)
        self.assertEqual(divide(0, 5), 0)
        with self.assertRaises(ValueError):
            divide(5, 0)


class TestFactorialFunction(unittest.TestCase):
    def test_factorial_zero(self):
        self.assertEqual(factorial(0), 1)

    def test_factorial_positive_numbers(self):
        self.assertEqual(factorial(1), 1)
        self.assertEqual(factorial(5), 120)
        self.assertEqual(factorial(10), 3628800)

    def test_factorial_negative_number(self):
        with self.assertRaises(ValueError):
            factorial(-1)


class TestIsPrimeFunction(unittest.TestCase):
    def test_is_prime_negative_and_zero(self):
        self.assertFalse(is_prime(-5))
        self.assertFalse(is_prime(0))

    def test_is_prime_one(self):
        self.assertFalse(is_prime(1))

    def test_is_prime_small_primes(self):
        self.assertTrue(is_prime(2))
        self.assertTrue(is_prime(3))
        self.assertTrue(is_prime(5))
        self.assertTrue(is_prime(7))
        self.assertTrue(is_prime(11))
        self.assertTrue(is_prime(13))

    def test_is_prime_small_non_primes(self):
        self.assertFalse(is_prime(4))
        self.assertFalse(is_prime(6))
        self.assertFalse(is_prime(8))
        self.assertFalse(is_prime(9))
        self.assertFalse(is_prime(10))

    def test_is_prime_larger_numbers(self):
        self.assertTrue(is_prime(17))
        self.assertTrue(is_prime(19))
        self.assertTrue(is_prime(23))
        self.assertFalse(is_prime(25))
        self.assertFalse(is_prime(100))


class TestFibonacciFunction(unittest.TestCase):
    def test_fibonacci_negative(self):
        with self.assertRaises(ValueError):
            fibonacci(-1)

    def test_fibonacci_zero_and_one(self):
        self.assertEqual(fibonacci(0), 0)
        self.assertEqual(fibonacci(1), 1)

    def test_fibonacci_sequence(self):
        self.assertEqual(fibonacci(2), 1)
        self.assertEqual(fibonacci(3), 2)
        self.assertEqual(fibonacci(4), 3)
        self.assertEqual(fibonacci(5), 5)
        self.assertEqual(fibonacci(6), 8)
        self.assertEqual(fibonacci(10), 55)


class TestCalculatorClass(unittest.TestCase):
    def test_calculator_initialization(self):
        calc = Calculator()
        self.assertEqual(calc.memory, 0)

    def test_calculator_basic_operations(self):
        calc = Calculator()
        self.assertEqual(calc.add(5, 3), 8)
        self.assertEqual(calc.subtract(10, 4), 6)
        self.assertEqual(calc.multiply(3, 4), 12)
        self.assertEqual(calc.divide(10, 2), 5)

    def test_calculator_divide_by_zero(self):
        calc = Calculator()
        with self.assertRaises(ValueError):
            calc.divide(5, 0)

    def test_calculator_memory_operations(self):
        calc = Calculator()
        calc.store(42)
        self.assertEqual(calc.memory, 42)
        self.assertEqual(calc.recall(), 42)

        calc.store(100)
        self.assertEqual(calc.recall(), 100)


class TestStringManipulatorClass(unittest.TestCase):
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
        self.assertFalse(StringManipulator.is_palindrome("Python"))


class TestDataProcessorClass(unittest.TestCase):
    def test_data_processor_initialization(self):
        processor = DataProcessor([1, 2, 3, 4, 5])
        self.assertEqual(processor.data, [1, 2, 3, 4, 5])

        with self.assertRaises(ValueError):
            DataProcessor([])

    def test_get_mean(self):
        processor = DataProcessor([1, 2, 3, 4, 5])
        self.assertEqual(processor.get_mean(), 3.0)

        processor = DataProcessor([10, 20, 30])
        self.assertEqual(processor.get_mean(), 20.0)

    def test_get_variance(self):
        processor = DataProcessor([1, 2, 3, 4, 5])
        self.assertEqual(processor.get_variance(), 2.5)

        with self.assertRaises(ValueError):
            DataProcessor([5]).get_variance()

    def test_normalize(self):
        processor = DataProcessor([1, 2, 3, 4, 5])
        normalized = processor.normalize()
        expected = [-1.264911064067352, -0.6324555320336759, 0.0, 0.6324555320336759, 1.264911064067352]
        
        # Check each value with a small tolerance for floating point precision
        for actual, expected_val in zip(normalized, expected):
            self.assertAlmostEqual(actual, expected_val, places=10)

        # Test error case with zero standard deviation
        processor = DataProcessor([5, 5, 5])
        with self.assertRaises(ValueError):
            processor.normalize()


class TestDateParsingFunction(unittest.TestCase):
    def test_parse_date_default_format(self):
        date_str = "2023-10-15"
        expected = datetime(2023, 10, 15)
        self.assertEqual(parse_date(date_str), expected)

    def test_parse_date_custom_format(self):
        date_str = "15/10/2023"
        custom_format = "%d/%m/%Y"
        expected = datetime(2023, 10, 15)
        self.assertEqual(parse_date(date_str, custom_format), expected)

    def test_parse_date_invalid_format(self):
        date_str = "not-a-date"
        with self.assertRaises(ValueError):
            parse_date(date_str)


class TestSafeListAccessFunction(unittest.TestCase):
    def test_safe_list_access_valid_index(self):
        lst = [10, 20, 30, 40, 50]
        self.assertEqual(safe_list_access(lst, 0), 10)
        self.assertEqual(safe_list_access(lst, 2), 30)
        self.assertEqual(safe_list_access(lst, 4), 50)

    def test_safe_list_access_invalid_index(self):
        lst = [10, 20, 30]
        self.assertIsNone(safe_list_access(lst, 5))
        self.assertIsNone(safe_list_access(lst, -5))

    def test_safe_list_access_with_default(self):
        lst = [10, 20, 30]
        self.assertEqual(safe_list_access(lst, 5, "default"), "default")
        self.assertEqual(safe_list_access(lst, -5, 999), 999)


class TestMergeDictsFunction(unittest.TestCase):
    def test_merge_dicts_basic(self):
        dict1 = {"a": 1, "b": 2}
        dict2 = {"c": 3, "d": 4}
        result = merge_dicts(dict1, dict2)
        self.assertEqual(result, {"a": 1, "b": 2, "c": 3, "d": 4})

    def test_merge_dicts_with_overwrite(self):
        dict1 = {"a": 1, "b": 2}
        dict2 = {"b": 3, "c": 4}
        result = merge_dicts(dict1, dict2)
        self.assertEqual(result, {"a": 1, "b": 3, "c": 4})

    def test_merge_dicts_with_nested_dicts(self):
        dict1 = {"a": 1, "b": {"x": 10, "y": 20}}
        dict2 = {"c": 3, "b": {"y": 30, "z": 40}}
        result = merge_dicts(dict1, dict2)
        self.assertEqual(result, {"a": 1, "b": {"x": 10, "y": 30, "z": 40}, "c": 3})

    def test_merge_dicts_with_nested_non_dict_overwrite(self):
        dict1 = {"a": 1, "b": {"x": 10}}
        dict2 = {"b": 20}
        result = merge_dicts(dict1, dict2)
        self.assertEqual(result, {"a": 1, "b": 20})


if __name__ == "__main__":
    unittest.main()