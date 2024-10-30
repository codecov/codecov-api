from textblob import TextBlob

class SentimentAnalyzer:
    def __init__(self):
        pass
    
    def get_sentiment(self, sentence: str) -> str:
        polarity = self._get_polarity(sentence)
        if polarity > 0:
            return "positive"
        elif polarity < 0:
            return "negative"
        else:
            return "neutral"
    
    def get_polarity_score(self, sentence: str) -> float:
        return self._get_polarity(sentence)
    
    def get_subjectivity_score(self, sentence: str) -> float:
        return self._get_subjectivity(sentence)
    
    def is_neutral(self, sentence: str) -> bool:
        return self.get_sentiment(sentence) == "neutral"
    
    def is_positive(self, sentence: str) -> bool:
        return self.get_sentiment(sentence) == "positive"

    def _get_polarity(self, sentence: str) -> float:
        analysis = TextBlob(sentence)
        return analysis.sentiment.polarity
    
    def _get_subjectivity(self, sentence: str) -> float:
        analysis = TextBlob(sentence)
        return analysis.sentiment.subjectivity
