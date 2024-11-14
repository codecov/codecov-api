from unittest.mock import patch

import pytest

from codecov.sentiment import SentimentAnalyzer


@pytest.fixture
def sentiment_analyzer():
    return SentimentAnalyzer()


@patch("codecov.sentiment.TextBlob")
def test_get_sentiment_positive(mock_textblob, sentiment_analyzer):
    mock_textblob.return_value.sentiment.polarity = 0.5
    assert sentiment_analyzer.get_sentiment("Great job!") == "positive"


@patch("codecov.sentiment.TextBlob")
def test_get_sentiment_negative(mock_textblob, sentiment_analyzer):
    mock_textblob.return_value.sentiment.polarity = -0.5
    assert sentiment_analyzer.get_sentiment("Terrible experience.") == "negative"


@patch("codecov.sentiment.TextBlob")
def test_get_sentiment_neutral(mock_textblob, sentiment_analyzer):
    mock_textblob.return_value.sentiment.polarity = 0.0
    assert sentiment_analyzer.get_sentiment("This is a neutral statement.") == "neutral"


@patch("codecov.sentiment.TextBlob")
def test_get_polarity_score(mock_textblob, sentiment_analyzer):
    mock_textblob.return_value.sentiment.polarity = 0.75
    assert sentiment_analyzer.get_polarity_score("Excellent work!") == 0.75


@patch("codecov.sentiment.TextBlob")
def test_get_subjectivity_score(mock_textblob, sentiment_analyzer):
    mock_textblob.return_value.sentiment.subjectivity = 0.6
    assert sentiment_analyzer.get_subjectivity_score("I think this is amazing!") == 0.6


@patch("codecov.sentiment.TextBlob")
def test_is_neutral_true(mock_textblob, sentiment_analyzer):
    mock_textblob.return_value.sentiment.polarity = 0.0
    assert sentiment_analyzer.is_neutral("This is a fact.") == True


@patch("codecov.sentiment.TextBlob")
def test_is_neutral_false(mock_textblob, sentiment_analyzer):
    mock_textblob.return_value.sentiment.polarity = 0.5
    assert sentiment_analyzer.is_neutral("This is great!") == False


@patch("codecov.sentiment.TextBlob")
def test_is_positive_true(mock_textblob, sentiment_analyzer):
    mock_textblob.return_value.sentiment.polarity = 0.5
    assert sentiment_analyzer.is_positive("This is wonderful!") == True


@patch("codecov.sentiment.TextBlob")
def test_is_positive_false(mock_textblob, sentiment_analyzer):
    mock_textblob.return_value.sentiment.polarity = -0.5
    assert sentiment_analyzer.is_positive("This is awful.") == False


@patch("codecov.sentiment.TextBlob")
def test_private_get_polarity(mock_textblob, sentiment_analyzer):
    mock_textblob.return_value.sentiment.polarity = 0.8
    assert sentiment_analyzer._get_polarity("Amazing!") == 0.8


@patch("codecov.sentiment.TextBlob")
def test_private_get_subjectivity(mock_textblob, sentiment_analyzer):
    mock_textblob.return_value.sentiment.subjectivity = 0.9
    assert sentiment_analyzer._get_subjectivity("I absolutely love this!") == 0.9