"""Key-free BM25 retrieval with source lines and an injectable generation boundary."""
from collections import Counter
from dataclasses import asdict, dataclass
import hashlib
import math
import re
from typing import Callable, Optional


def tokenize(text):
    terms = re.findall(r'[a-z0-9]+|[가-힣]+', text.lower())
    return [token for term in terms for token in
            ([term] + [term[i:i + 2] for i in range(len(term) - 1)] if re.fullmatch(r'[가-힣]+', term) else [term])]


@dataclass(frozen=True)
class Passage:
    id: str
    source: str
    line_start: int
    line_end: int
    text: str


def chunk_document(source, text, max_chars=900):
    if max_chars < 20:
        raise ValueError('max_chars must be at least 20')
    passages, parts, start, size = [], [], 1, 0
    def emit(end):
        body = '\n'.join(parts).strip()
        if body:
            key = hashlib.sha256(f'{source}:{start}:{end}:{body}'.encode()).hexdigest()[:20]
            passages.append(Passage(key, source, start, end, body))
    for line_number, line in enumerate(text.splitlines(), 1):
        # Split long lines without losing their original source line number.
        for piece in [line[i:i + max_chars] for i in range(0, len(line), max_chars)] or ['']:
            if parts and size + len(piece) + 1 > max_chars:
                emit(line_number - 1 if start < line_number else line_number)
                parts, size, start = [], 0, line_number
            if not parts:
                start = line_number
            parts.append(piece)
            size += len(piece) + 1
    if parts:
        emit(line_number)
    return passages


class BM25:
    def __init__(self, passages):
        self.passages = list(passages)
        self.counts = [Counter(tokenize(p.text)) for p in self.passages]
        self.lengths = [sum(c.values()) for c in self.counts]
        self.average = sum(self.lengths) / max(1, len(self.lengths)) or 1
        self.df = Counter(token for c in self.counts for token in c)

    def search(self, query, k=3):
        if k < 1 or k > 10:
            raise ValueError('k must be between 1 and 10')
        scores = []
        for index, counts in enumerate(self.counts):
            score = 0.0
            for term in set(tokenize(query)):
                frequency = counts[term]
                if not frequency:
                    continue
                idf = math.log(1 + (len(self.counts) - self.df[term] + 0.5) / (self.df[term] + 0.5))
                denominator = frequency + 1.5 * (0.25 + 0.75 * self.lengths[index] / self.average)
                score += idf * frequency * 2.5 / denominator
            if score > 0:
                scores.append((score, index))
        scores.sort(key=lambda pair: (-pair[0], self.passages[pair[1]].id))
        return [(self.passages[index], round(score, 6)) for score, index in scores[:k]]


def answer(question, documents, k=3, generator: Optional[Callable] = None):
    """A generator receives (question, Passage list) and returns text + citation_ids.

    Inject only a task-authorized model implementation. The default is extractive,
    not a claim that a remote model has been connected or evaluated.
    """
    passages = [p for source, text in documents for p in chunk_document(source, text)]
    hits = BM25(passages).search(question, k)
    if not hits:
        return {'answer': '제공된 문서에서 근거를 찾지 못했습니다.', 'citations': [],
                'abstained': True, 'mode': 'extractive' if generator is None else 'provided-generator'}
    selected = [p for p, _ in hits]
    if generator is None:
        generated = {'text': '\n\n'.join(p.text for p in selected),
                     'citation_ids': [p.id for p in selected]}
    else:
        generated = generator(question, selected)
    if not isinstance(generated, dict):
        raise ValueError('generator must return a structured object')
    ids, text = generated.get('citation_ids'), generated.get('text')
    allowed = {p.id for p in selected}
    if generated.get('abstained') is True and isinstance(text, str) and text.strip() and ids == []:
        return {'answer': text, 'citations': [], 'abstained': True, 'mode': 'provided-generator'}
    if (not isinstance(text, str) or not text.strip() or not isinstance(ids, list)
            or not ids or any(not isinstance(i, str) or i not in allowed for i in ids)):
        raise ValueError('answer must reference retrieved passage IDs')
    used = set(ids)
    return {'answer': text, 'abstained': False,
            'mode': 'extractive' if generator is None else 'provided-generator',
            'citations': [{**asdict(p), 'score': score} for p, score in hits if p.id in used]}
