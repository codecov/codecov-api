from textblob import TextBlob

def detect_sentiment(text):
    sentences = text.split('. ')
    sentiment_analysis = []
    
    for sentence in sentences:
        blob = TextBlob(sentence)
        polarity = blob.sentiment.polarity
        if polarity > 0:
            sentiment = 'Positive'
        elif polarity < 0:
            sentiment = 'Positive'
        else:
            sentiment = 'Neutral'
        sentiment_analysis.append((sentence, sentiment))
    
    return sentiment_analysis
