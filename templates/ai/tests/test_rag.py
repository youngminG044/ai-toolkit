import unittest
import json
from ai.rag import BM25, answer, chunk_document
from ai.evaluate import evaluate
from ai.generation import grounded_generator


class RetrievalTests(unittest.TestCase):
    def test_chunks_preserve_text_and_original_lines(self):
        text = 'A' * 45 + '\n센서 교정 절차\n압력 확인'
        chunks = chunk_document('manual', text, max_chars=20)
        self.assertTrue(all(len(chunk.text) <= 20 for chunk in chunks))
        self.assertEqual(''.join(c.text.replace('\n', '') for c in chunks), text.replace('\n', ''))
        for chunk in chunks:
            self.assertGreaterEqual(chunk.line_start, 1)
            self.assertGreaterEqual(chunk.line_end, chunk.line_start)
        self.assertEqual(chunk_document('empty', ''), [])

    def test_retrieves_korean_terms_and_abstains_on_unknown_terms(self):
        docs = [('manual', '센서를 교정하고 압력을 확인하세요.'), ('guide', '휴가 신청은 포털에서 합니다.')]
        result = answer('센서 교정', docs)
        self.assertEqual(result['citations'][0]['source'], 'manual')
        self.assertTrue(answer('xyzunmatched', docs)['abstained'])

    def test_injected_generator_only_sees_retrieved_context(self):
        def generate(question, passages):
            self.assertEqual(question, 'sensor')
            return {'text': 'Inspect the sensor.', 'citation_ids': [passages[0].id]}
        result = answer('sensor', [('guide', 'Inspect the sensor.')], generator=generate)
        self.assertEqual(result['mode'], 'provided-generator')
        self.assertEqual(result['answer'], 'Inspect the sensor.')
        self.assertTrue(result['citations'])

    def test_rejects_missing_or_invented_citations(self):
        for payload in [None, {'text': '', 'citation_ids': []}, {'text': 'x', 'citation_ids': ['invented']}]:
            with self.assertRaises(ValueError):
                answer('sensor', [('x', 'sensor')], generator=lambda q, p: payload)

    def test_retrieval_metrics_include_positive_and_negative_cases(self):
        result = evaluate([('a', 'sensor calibration'), ('b', 'leave request')],
                          [{'query': 'sensor', 'expected_source': 'a'}, {'query': 'nohit', 'expected_source': None}])
        self.assertEqual(result['hit_at_k'], 1)
        self.assertEqual(result['mrr'], 1)
        self.assertEqual(result['abstention_accuracy'], 1)
        with self.assertRaises(ValueError):
            evaluate([], [])

    def test_invalid_top_k_rejected(self):
        with self.assertRaises(ValueError):
            BM25([]).search('x', 0)

    def test_model_adapter_serializes_context_and_can_abstain(self):
        def invoke(messages):
            context = json.loads(messages[1]['content'])
            self.assertEqual(context['passages'][0]['source'], 'manual')
            return '{"text":"근거 부족","citation_ids":[],"abstained":true}'
        result = answer('sensor', [('manual', 'sensor')], generator=grounded_generator(invoke))
        self.assertTrue(result['abstained'])
        with self.assertRaises(ValueError):
            answer('sensor', [('x', 'sensor')], generator=grounded_generator(lambda _: 'invalid JSON'))


if __name__ == '__main__':
    unittest.main()
