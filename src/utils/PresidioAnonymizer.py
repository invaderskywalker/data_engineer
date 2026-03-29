

from langchain_experimental.data_anonymizer import PresidioReversibleAnonymizer


def prcoessWords(word):
    word = word.strip()
    return word


def findLabels(data):
    result = {}
    for d in data:
        word = prcoessWords(d['word'])
        result[word] = d['entity_group']
    return result


class PresidioAnonymizer():
    def __init__(self):
        self._name = "PII Anonymizer"
        self.entity_map = {}
        self.anonymized_data = {}
        self.deanonymizer_mapping = None
        self.excluded_entities = [
            "<DATE>", '<TIME>', '<DATE_TIME>', '<PERSON>', '<NRP>']
        self.anonymizer = PresidioReversibleAnonymizer(
            add_default_faker_operators=False,
            languages_config={
                # You can also use Stanza or transformers library.
                # See https://microsoft.github.io/presidio/analyzer/customizing_nlp_models/
                "nlp_engine_name": "spacy",
                "models": [
                    {"lang_code": "en", "model_name": "en_core_web_sm"},
                    # {"lang_code": "de", "model_name": "de_core_news_md"},
                    # {"lang_code": "es", "model_name": "es_core_news_md"},
                    # ...
                    # List of available models: https://spacy.io/usage/models
                ],
            }
            # analyzed_fields=["PHONE_NUMBER", "EMAIL_ADDRESS", "CREDIT_CARD", "PERSON"],
        )
        # self._model = pipeline("token-classification", model_id, device=-1)

    def anonymizeString(self, text):
        print("anonymizeString debug", text)
        self.anonymizer.anonymize(text)
        self.deanonymizer_mapping = self.anonymizer.deanonymizer_mapping

        labels = {}
        for k, v in self.anonymizer.deanonymizer_mapping.items():
            # print(v)
            labels.update(v)

        labels = {v: k for k, v in labels.items()}
        # print("----", labels)

        counter = 1
        newText = text

        for name, label in labels.items():
            if label in self.excluded_entities:
                continue
            anonymized_label = label
            self.anonymized_data[name] = anonymized_label
            self.entity_map[anonymized_label] = name
            counter = counter + 1
            newText = newText.replace(name, anonymized_label, 1)
        return newText

    def deanonymizeString(self, text):
        print("deanonymizeString debug")
        nText = text
        for k, v in self.entity_map.items():
            nText = nText.replace(k, v, 1)
        return nText
