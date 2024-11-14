import unittest
from codecov.sentiment import SentimentAnalyzer

class TestSentimentAnalyzer(unittest.TestCase):
    def setUp(self):
        self.analyzer = SentimentAnalyzer()

    def test_get_sentiment(self):
        self.assertEqual(self.analyzer.get_sentiment("I love this product!"), "positive")
        self.assertEqual(self.analyzer.get_sentiment("I hate this product."), "negative")
        self.assertEqual(self.analyzer.get_sentiment("The product is okay."), "neutral")

    def test_get_polarity_score(self):
        self.assertGreater(self.analyzer.get_polarity_score("I love this product!"), 0)
        self.assertLess(self.analyzer.get_polarity_score("I hate this product."), 0)
        self.assertAlmostEqual(self.analyzer.get_polarity_score("The product is okay."), 0, delta=0.1)

    def test_get_subjectivity_score(self):
        self.assertGreater(self.analyzer.get_subjectivity_score("I absolutely love this amazing product!"), 0.5)
        self.assertLess(self.analyzer.get_subjectivity_score("The product weighs 100 grams."), 0.5)

    def test_is_neutral(self):
        self.assertTrue(self.analyzer.is_neutral("The product is okay."))
        self.assertFalse(self.analyzer.is_neutral("I love this product!"))
        self.assertFalse(self.analyzer.is_neutral("I hate this product."))

    def test_is_positive(self):
        self.assertTrue(self.analyzer.is_positive("I love this product!"))
        self.assertFalse(self.analyzer.is_positive("I hate this product."))
        self.assertFalse(self.analyzer.is_positive("The product is okay."))

    def test_empty_string(self):
        self.assertEqual(self.analyzer.get_sentiment(""), "neutral")
        self.assertEqual(self.analyzer.get_polarity_score(""), 0)
        self.assertEqual(self.analyzer.get_subjectivity_score(""), 0)
        self.assertTrue(self.analyzer.is_neutral(""))
        self.assertFalse(self.analyzer.is_positive(""))

    def test_non_string_input(self):
        with self.assertRaises(AttributeError):
            self.analyzer.get_sentiment(123)
        with self.assertRaises(AttributeError):
            self.analyzer.get_polarity_score(None)
        with self.assertRaises(AttributeError):
            self.analyzer.get_subjectivity_score([])
        with self.assertRaises(AttributeError):
            self.analyzer.is_neutral({})
        with self.assertRaises(AttributeError):
            self.analyzer.is_positive(True)

if __name__ == '__main__':
    unittest.main()