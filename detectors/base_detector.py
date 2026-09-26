from dataclasses import dataclass


@dataclass
class Finding:
    file: str
    line: int
    category: str
    severity: str
    description: str
    suggestion: str
    score: int = 0
