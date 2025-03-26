import unittest
from datetime import datetime
from api.gen_ai.math import (
    add, subtract, divide, factorial, is_prime, fibonacci,
    Calculator, StringManipulator, DataProcessor, parse_date,
    safe_list_access, merge_dicts
)


class TestBasicArithmeticFunctions(unittest.TestCase):
    def test_add(self):
        self.assertEqual(add(1, 2), 3)
        self.assertEqual(add(-1, 1), 0)
        self.assertEqual(add(0, 0), 0)
        self.assertEqual(add(10.5, 20.5), 31.0)

    def test_subtract(self):
        self.assertEqual(subtract(5, 3), 2)
        self.assertEqual(subtract(5, 10), -5)
        self.assertEqual(subtract(0, 0), 0)
        self.assertEqual(subtract(10.5, 0.5), 10.0)

    def test_divide(self):
        self.assertEqual(divide(10, 2), 5)
        self.assertEqual(divide(10, 3), 10/3)
        self.assertEqual(divide(-10, 2), -5)
        self.assertEqual(divide(0, 5), 0)
        
        # Test division by zero raises ValueError
        with self.assertRaises(ValueError):
            divide(10, 0)


class TestFactorial(unittest.TestCase):
    def test_factorial_with_valid_input(self):
        self.assertEqual(factorial(0), 1)
        self.assertEqual(factorial(1), 1)
        self.assertEqual(factorial(5), 120)
        self.assertEqual(factorial(10), 3628800)

    def test_factorial_with_negative_input(self):
        with self.assertRaises(ValueError):
            factorial(-1)


class TestIsPrime(unittest.TestCase):
    def test_is_prime_with_prime_numbers(self):
        prime_numbers = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31]
        for num in prime_numbers:
            self.assertTrue(is_prime(num), f"{num} should be identified as prime")

    def test_is_prime_with_non_prime_numbers(self):
        non_prime_numbers = [0, 1, 4, 6, 8, 9, 10, 12, 14, 15, 16, 18, 20, 21]
        for num in non_prime_numbers:
            self.assertFalse(is_prime(num), f"{num} should not be identified as prime")


class TestFibonacci(unittest.TestCase):
    def test_fibonacci_with_valid_input(self):
        # First 10 Fibonacci numbers
        expected_sequence = [0, 1, 1, 2, 3, 5, 8, 13, 21, 34]
        for n, expected in enumerate(expected_sequence):
            self.assertEqual(fibonacci(n), expected, f"fibonacci({n}) should return {expected}")

    def test_fibonacci_with_negative_input(self):
        with self.assertRaises(ValueError):
            fibonacci(-1)


class TestCalculator(unittest.TestCase):
    def setUp(self):
        self.calculator = Calculator()

    def test_add(self):
        self.assertEqual(self.calculator.add(10, 5), 15)
        self.assertEqual(self.calculator.add(-10, -5), -15)

    def test_subtract(self):
        self.assertEqual(self.calculator.subtract(10, 5), 5)
        self.assertEqual(self.calculator.subtract(-10, -5), -5)

    def test_multiply(self):
        self.assertEqual(self.calculator.multiply(10, 5), 50)
        self.assertEqual(self.calculator.multiply(-10, -5), 50)
        self.assertEqual(self.calculator.multiply(-10, 5), -50)

    def test_divide(self):
        self.assertEqual(self.calculator.divide(10, 5), 2)
        self.assertEqual(self.calculator.divide(-10, -5), 2)
        self.assertEqual(self.calculator.divide(-10, 5), -2)
        
        # Test division by zero
        with self.assertRaises(ValueError):
            self.calculator.divide(10, 0)

    def test_memory_functions(self):
        # Default memory value
        self.assertEqual(self.calculator.memory, 0)
        self.assertEqual(self.calculator.recall(), 0)
        
        # Store and recall
        self.calculator.store(42)
        self.assertEqual(self.calculator.memory, 42)
        self.assertEqual(self.calculator.recall(), 42)
        
        # Store negative number
        self.calculator.store(-17)
        self.assertEqual(self.calculator.recall(), -17)


class TestStringManipulator(unittest.TestCase):
    def test_reverse_string(self):
        self.assertEqual(StringManipulator.reverse_string("hello"), "olleh")
        self.assertEqual(StringManipulator.reverse_string(""), "")
        self.assertEqual(StringManipulator.reverse_string("a"), "a")
        self.assertEqual(StringManipulator.reverse_string("12345"), "54321")

    def test_is_palindrome(self):
        # Test true palindromes
        palindromes = ["", "a", "aa", "aba", "racecar", "A man, a plan, a canal: Panama"]
        for text in palindromes:
            self.assertTrue(StringManipulator.is_palindrome(text), f"'{text}' should be identified as a palindrome")
        
        # Test non-palindromes
        non_palindromes = ["ab", "abca", "hello", "world"]
        for text in non_palindromes:
            self.assertFalse(StringManipulator.is_palindrome(text), f"'{text}' should not be identified as a palindrome")


class TestDataProcessor(unittest.TestCase):
    def test_initialization_with_valid_data(self):
        processor = DataProcessor([1, 2, 3, 4, 5])
        self.assertEqual(processor.data, [1, 2, 3, 4, 5])

    def test_initialization_with_empty_list(self):
        with self.assertRaises(ValueError):
            DataProcessor([])

    def test_get_mean(self):
        processor = DataProcessor([1, 2, 3, 4, 5])
        self.assertEqual(processor.get_mean(), 3)
        
        processor = DataProcessor([10, 20, 30, 40])
        self.assertEqual(processor.get_mean(), 25)

    def test_get_variance(self):
        processor = DataProcessor([1, 2, 3, 4, 5])
        self.assertEqual(processor.get_variance(), 2.5)
        
        processor = DataProcessor([10, 10, 10, 10])
        self.assertEqual(processor.get_variance(), 0)

    def test_get_variance_with_single_element(self):
        processor = DataProcessor([42])
        with self.assertRaises(ValueError):
            processor.get_variance()

    def test_normalize(self):
        processor = DataProcessor([1, 2, 3, 4, 5])
        expected = [-1.264911, -0.632456, 0.0, 0.632456, 1.264911]
        result = processor.normalize()
        
        # Check each element with a small tolerance for floating point comparison
        for i in range(len(expected)):
            self.assertAlmostEqual(result[i], expected[i], places=5)

    def test_normalize_with_zero_variance(self):
        processor = DataProcessor([10, 10, 10, 10])
        with self.assertRaises(ValueError):
            processor.normalize()


class TestDateParsing(unittest.TestCase):
    def test_parse_date_with_default_format(self):
        result = parse_date("2023-04-15")
        self.assertEqual(result, datetime(2023, 4, 15))

    def test_parse_date_with_custom_format(self):
        result = parse_date("15/04/2023", fmt="%d/%m/%Y")
        self.assertEqual(result, datetime(2023, 4, 15))

    def test_parse_date_with_invalid_format(self):
        with self.assertRaises(ValueError):
            parse_date("2023/04/15")  # Doesn't match default format

    def test_parse_date_with_invalid_date(self):
        with self.assertRaises(ValueError):
            parse_date("2023-13-45")  # Invalid month and day


class TestSafeListAccess(unittest.TestCase):
    def test_safe_list_access_with_valid_index(self):
        test_list = [10, 20, 30, 40, 50]
        
        self.assertEqual(safe_list_access(test_list, 0), 10)
        self.assertEqual(safe_list_access(test_list, 2), 30)
        self.assertEqual(safe_list_access(test_list, 4), 50)

    def test_safe_list_access_with_invalid_index(self):
        test_list = [10, 20, 30]
        
        # Test with default value (None)
        self.assertIsNone(safe_list_access(test_list, 5))
        self.assertIsNone(safe_list_access(test_list, -5))
        
        # Test with custom default value
        self.assertEqual(safe_list_access(test_list, 10, default="not found"), "not found")


class TestMergeDicts(unittest.TestCase):
    def test_merge_dicts_with_non_overlapping_keys(self):
        dict1 = {"a": 1, "b": 2}
        dict2 = {"c": 3, "d": 4}
        
        result = merge_dicts(dict1, dict2)
        expected = {"a": 1, "b": 2, "c": 3, "d": 4}
        
        self.assertEqual(result, expected)

    def test_merge_dicts_with_overlapping_keys(self):
        dict1 = {"a": 1, "b": 2, "c": 3}
        dict2 = {"b": 5, "d": 4}
        
        result = merge_dicts(dict1, dict2)
        expected = {"a": 1, "b": 5, "c": 3, "d": 4}
        
        self.assertEqual(result, expected)

    def test_merge_dicts_with_nested_dicts(self):
        dict1 = {"a": 1, "b": {"x": 10, "y": 20}}
        dict2 = {"c": 3, "b": {"y": 30, "z": 40}}
        
        result = merge_dicts(dict1, dict2)
        expected = {"a": 1, "b": {"x": 10, "y": 30, "z": 40}, "c": 3}
        
        self.assertEqual(result, expected)