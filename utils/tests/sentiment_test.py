import unittest
from utils.sentiment import detect_sentiment

class TestSentimentAnalysis(unittest.TestCase):
    def test_positive_sentiment(self):
        text = "I love this product. It's amazing."
        result = detect_sentiment(text)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0][1], 'Positive')
        self.assertEqual(result[1][1], 'Positive')

    def test_negative_sentiment(self):
        text = "This is terrible. I hate it."
        result = detect_sentiment(text)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0][1], 'Negative')
        self.assertEqual(result[1][1], 'Negative')

    def test_neutral_sentiment(self):
        text = "The sky is blue. Water is wet."
        result = detect_sentiment(text)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0][1], 'Neutral')
        self.assertEqual(result[1][1], 'Neutral')

    def test_mixed_sentiment(self):
        text = "I love this product. However, the price is too high."
        result = detect_sentiment(text)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0][1], 'Positive')
        self.assertEqual(result[1][1], 'Negative')

    def test_empty_input(self):
        text = ""
        result = detect_sentiment(text)
        self.assertEqual(len(result), 0)

    def test_single_word(self):
        text = "Fantastic"
        result = detect_sentiment(text)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][1], 'Positive')

if __name__ == '__main__':
    unittest.main()