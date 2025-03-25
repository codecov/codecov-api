import math
from statistics import mean, variance
from datetime import datetime

# Basic arithmetic functions
def add(a, b):
    return a + b

def subtract(a, b):
    return a - b

def divide(a, b):
    if b == 0:
        raise ValueError("Division by zero is not allowed")
    return a / b

# Factorial using iterative approach
def factorial(n):
    if n < 0:
        raise ValueError("Negative numbers do not have factorials")
    result = 1
    for i in range(1, n + 1):
        result *= i
    return result

# Check if a number is prime
def is_prime(n):
    if n <= 1:
        return False
    if n <= 3:
        return True
    if n % 2 == 0 or n % 3 == 0:
        return False
    i = 5
    while i * i <= n:
        if n % i == 0 or n % (i + 2) == 0:
            return False
        i += 6
    return True

# Fibonacci number generator (nth number)
def fibonacci(n):
    if n < 0:
        raise ValueError("n must be a non-negative integer")
    if n == 0:
        return 0
    elif n == 1:
        return 1
    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b

# Calculator class with memory
class Calculator:
    def __init__(self):
        self.memory = 0

    def add(self, a, b):
        return a + b

    def subtract(self, a, b):
        return a - b

    def multiply(self, a, b):
        return a * b

    def divide(self, a, b):
        if b == 0:
            raise ValueError("Cannot divide by zero")
        return a / b

    def store(self, value):
        self.memory = value

    def recall(self):
        return self.memory

# String manipulation functions
class StringManipulator:
    @staticmethod
    def reverse_string(s):
        return s[::-1]

    @staticmethod
    def is_palindrome(s):
        cleaned = ''.join(c.lower() for c in s if c.isalnum())
        return cleaned == cleaned[::-1]

# Data processing class for numerical lists
class DataProcessor:
    def __init__(self, data):
        if not data:
            raise ValueError("Data list cannot be empty")
        self.data = data

    def get_mean(self):
        return mean(self.data)

    def get_variance(self):
        if len(self.data) < 2:
            raise ValueError("At least two data points are required to compute variance")
        return variance(self.data)

    def normalize(self):
        m = self.get_mean()
        try:
            std_dev = math.sqrt(variance(self.data))
        except Exception:
            raise ValueError("Could not compute standard deviation")
        if std_dev == 0:
            raise ValueError("Standard deviation is zero, cannot normalize.")
        return [(x - m) / std_dev for x in self.data]

# Date parsing function with a default format
def parse_date(date_str, fmt="%Y-%m-%d"):
    try:
        return datetime.strptime(date_str, fmt)
    except ValueError:
        raise ValueError("Incorrect date format, should be YYYY-MM-DD")

# Safe access to list elements with default value
def safe_list_access(lst, index, default=None):
    try:
        return lst[index]
    except IndexError:
        return default

# Merge two dictionaries recursively
def merge_dicts(dict1, dict2):
    result = dict1.copy()
    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_dicts(result[key], value)
        else:
            result[key] = value
    return result

