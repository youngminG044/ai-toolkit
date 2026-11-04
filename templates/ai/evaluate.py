"""Evaluate retrieval on a caller-supplied, local JSON evaluation set."""
import argparse
import json
from pathlib import Path
from ai.rag import BM25, chunk_document


def evaluate(documents, cases, k=3):
    if not cases:
        raise ValueError('provide at least one evaluation case')
    index = BM25([p for name, text in documents for p in chunk_document(name, text)])
    hits, reciprocal, abstentions = 0, 0.0, 0
    for case in cases:
        sources = [p.source for p, _ in index.search(case['query'], k)]
        expected = case.get('expected_source')
        if expected is None:
            abstentions += not sources
            continue
        rank = next((i + 1 for i, source in enumerate(sources) if source == expected), None)
        hits += rank is not None
        reciprocal += 1 / rank if rank else 0
    positive = sum(case.get('expected_source') is not None for case in cases)
    negative = len(cases) - positive
    return {'cases': len(cases), 'retrieval_cases': positive, 'hit_at_k': hits / positive if positive else None,
            'mrr': reciprocal / positive if positive else None,
            'abstention_accuracy': abstentions / negative if negative else None,
            'scope': 'retrieval only; generated-answer correctness is separate'}


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('dataset', help='JSON: documents [{name,text}], cases [{query,expected_source|null}]')
    a = p.parse_args()
    data = json.loads(Path(a.dataset).read_text())
    print(json.dumps(evaluate([(d['name'], d['text']) for d in data['documents']], data['cases']), ensure_ascii=False, indent=2))
