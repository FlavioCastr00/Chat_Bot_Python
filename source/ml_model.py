import json
import random
from pathlib import Path

from sklearn.feature_extraction.text import CountVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline


class IntentClassifier:
    """
    Classificador simples de intenções usando Machine Learning.
    """

    def __init__(self, training_file, confidence_threshold=0.25):
        self.training_file = Path(training_file)
        self.confidence_threshold = confidence_threshold
        self.intents = []
        self.model = None
        self.train()

    def load_training_data(self):
        """
        Carrega o JSON de treinamento.
        """
        with open(self.training_file, "r", encoding="utf-8") as file:
            data = json.load(file)

        self.intents = data["intents"]
        return self.intents

    def prepare_examples(self):
        """
        Transforma o JSON em duas listas:

        texts:
            frases de exemplo que o usuário poderia digitar.

        labels:
            intenção correta de cada frase.
        """
        texts = []
        labels = []

        for intent in self.intents:
            tag = intent["tag"]

            for phrase in intent["patterns"]:
                texts.append(phrase)
                labels.append(tag)

        return texts, labels

    def train(self):
        """
        Treina o modelo.

        CountVectorizer:
            transforma texto em números com base nas palavras e pares de palavras.

        LogisticRegression:
            aprende a relação entre os números e as intenções.
        """
        self.load_training_data()
        texts, labels = self.prepare_examples()

        self.model = Pipeline(
            steps=[
                (
                    "vectorizer",
                    CountVectorizer(
                        lowercase=True,
                        strip_accents="unicode",
                        ngram_range=(1, 2),
                    ),
                ),
                (
                    "classifier",
                    LogisticRegression(
                        max_iter=1000,
                        class_weight="balanced",
                    ),
                ),
            ]
        )

        self.model.fit(texts, labels)

    def get_response(self, tag: str) -> str:
        """
        Retorna uma resposta-base para uma intenção.
        A resposta final pode ser complementada pelo front-end ou pelas rotas do Flask.
        """
        for intent in self.intents:
            if intent["tag"] == tag:
                return random.choice(intent["responses"])

        return "Não entendi sua solicitação. Digite ajuda para ver os comandos."

    def predict(self, message: str) -> dict:
        """
        Recebe uma mensagem e retorna:
        - intenção prevista;
        - confiança;
        - resposta-base.
        """
        message = (message or "").strip()

        if not message:
            return {
                "intent": "fallback",
                "confidence": 0.0,
                "response": "Digite uma mensagem para continuar.",
            }

        predicted_tag = str(self.model.predict([message])[0])
        probabilities = self.model.predict_proba([message])[0]
        confidence = float(max(probabilities))

        if confidence < self.confidence_threshold:
            predicted_tag = "fallback"

        return {
            "intent": predicted_tag,
            "confidence": round(confidence, 4),
            "response": self.get_response(predicted_tag),
        }


def carregar_classificador(training_file):
    """
    Função auxiliar para criar e treinar o classificador.
    """
    return IntentClassifier(training_file)
