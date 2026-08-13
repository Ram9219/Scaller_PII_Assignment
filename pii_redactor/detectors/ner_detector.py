import spacy
from typing import List
import logging
from core.entities import PIIEntity, EntityLocation
from config import CONFIDENCE_THRESHOLDS, ENABLED_ENTITIES

class NERDetector:
    def __init__(self, model_name="en_core_web_sm"):
        self.model_name = model_name
        self.nlp = None
        try:
            self.nlp = spacy.load(model_name)
        except OSError:
            logging.warning(f"spaCy model '{model_name}' not found. NER will be disabled.")
            logging.warning("Please install it using: python -m spacy download en_core_web_sm")

    def detect(self, text: str, location: EntityLocation, context: str = "") -> List[PIIEntity]:
        entities = []
        if not self.nlp or not text:
            return entities

        # Limit text length to prevent memory issues with massive strings, though docx runs/paragraphs are usually fine
        if len(text) > 100000:
            text = text[:100000]

        doc = self.nlp(text)
        
        for ent in doc.ents:
            # Map spaCy labels to our taxonomy candidates
            entity_type = None
            if ent.label_ == "PERSON" and "PERSON" in ENABLED_ENTITIES:
                entity_type = "PERSON"
            elif ent.label_ == "ORG" and "COMPANY" in ENABLED_ENTITIES:
                entity_type = "COMPANY_CANDIDATE" # Requires context validation
            elif ent.label_ == "GPE" or ent.label_ == "LOC":
                entity_type = "ADDRESS_CANDIDATE" # Not an address alone
                
            if entity_type:
                entities.append(PIIEntity(
                    text=ent.text,
                    entity_type=entity_type,
                    start=ent.start_char,
                    end=ent.end_char,
                    confidence=CONFIDENCE_THRESHOLDS["NER_MEDIUM"],
                    detector="spacy_ner",
                    location=location,
                    source_context=context
                ))
                
        return entities
