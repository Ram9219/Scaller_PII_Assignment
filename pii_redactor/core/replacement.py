from typing import Dict
from faker import Faker
from config import FAKER_SEED

class DeterministicReplacer:
    def __init__(self, seed: int = FAKER_SEED):
        self.fake = Faker('en_IN') # Indian locale for names, addresses, phones if possible
        self.fake.seed_instance(seed)
        self.mapping: Dict[str, str] = {}
        
    def _generate_fake(self, entity_type: str) -> str:
        if entity_type == "PERSON":
            return self.fake.name()
        elif entity_type == "EMAIL":
            # Safe placeholder domain
            return f"{self.fake.user_name()}@example.com"
        elif entity_type == "PHONE":
            # Generate a realistic Indian phone number
            return f"+91 {self.fake.msisdn()[3:13]}"
        elif entity_type == "COMPANY":
            return self.fake.company()
        elif entity_type == "PHYSICAL_OR_MAILING_ADDRESS":
            return self.fake.address().replace('\n', ', ')
        elif entity_type == "SSN":
            return self.fake.ssn()
        elif entity_type == "CREDIT_CARD":
            return self.fake.credit_card_number()
        elif entity_type == "DATE_OF_BIRTH" or entity_type == "DATE":
            return self.fake.date()
        elif entity_type == "IP_ADDRESS":
            return self.fake.ipv4()
        elif entity_type == "AADHAAR":
            return f"{self.fake.random_number(digits=4, fix_len=True)} {self.fake.random_number(digits=4, fix_len=True)} {self.fake.random_number(digits=4, fix_len=True)}"
        elif entity_type == "DIN":
            return str(self.fake.random_number(digits=8, fix_len=True))
        else:
            return f"[REDACTED {entity_type}]"

    def get_replacement(self, original_text: str, entity_type: str) -> str:
        """
        Returns a deterministic replacement for the original text.
        If we've seen this exact text before (ignoring case), return the same replacement.
        """
        key = original_text.lower()
        if key not in self.mapping:
            self.mapping[key] = self._generate_fake(entity_type)
        return self.mapping[key]
