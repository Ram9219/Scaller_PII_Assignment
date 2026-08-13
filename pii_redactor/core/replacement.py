import hashlib
from typing import Dict
from faker import Faker
from config import FAKER_SEED

class DeterministicReplacer:
    def __init__(self, seed: int = FAKER_SEED):
        self.base_seed = seed
        self.mapping: Dict[str, str] = {}
        
    def _generate_fake(self, original_text: str, entity_type: str) -> str:
        # Create a stable, order-independent seed combining base_seed, text, and type
        seed_string = f"{self.base_seed}|{original_text.lower()}|{entity_type}"
        # Use md5 to generate a 32-bit integer for the Faker seed
        seed_int = int(hashlib.md5(seed_string.encode('utf-8')).hexdigest()[:8], 16)
        
        fake = Faker('en_IN')
        fake.seed_instance(seed_int)
        
        if entity_type == "PERSON":
            return fake.name()
        elif entity_type == "EMAIL":
            return f"{fake.user_name()}@example.com"
        elif entity_type == "PHONE":
            return f"+91 {fake.msisdn()[3:13]}"
        elif entity_type == "COMPANY":
            return fake.company()
        elif entity_type == "PHYSICAL_OR_MAILING_ADDRESS":
            return fake.address().replace('\n', ', ')
        elif entity_type == "SSN":
            return fake.ssn()
        elif entity_type == "CREDIT_CARD":
            return fake.credit_card_number()
        elif entity_type in ["DATE_OF_BIRTH", "DATE"]:
            return fake.date()
        elif entity_type == "IP_ADDRESS":
            return fake.ipv4()
        elif entity_type == "AADHAAR":
            return f"{fake.random_number(digits=4, fix_len=True)} {fake.random_number(digits=4, fix_len=True)} {fake.random_number(digits=4, fix_len=True)}"
        elif entity_type == "DIN":
            return str(fake.random_number(digits=8, fix_len=True))
        else:
            return f"[REDACTED {entity_type}]"

    def get_replacement(self, original_text: str, entity_type: str) -> str:
        """
        Returns a deterministic replacement for the original text.
        If we've seen this exact text and type before, return the same replacement.
        """
        key = f"{original_text.lower()}|{entity_type}"
        if key not in self.mapping:
            self.mapping[key] = self._generate_fake(original_text, entity_type)
        return self.mapping[key]
