import { test } from 'node:test';
import assert from 'node:assert/strict';
import { summarize, bars, errorMessage } from './domain.mjs';

// assert는 실제 계산 결과와 미리 정한 기대값을 비교합니다. 다르면 테스트가 실패합니다.
test('화면 목록의 건수·완료 수·합계와 빈 목록의 0 처리를 확인한다', () => {
  // 준비: 2인 완료 항목 하나와 -3인 새 항목 하나. 기대값은 건수 2, 완료 1, 합계 2 + (-3) = -1입니다.
  // 서버 전체 목록/HTTP 응답은 이 검사 범위에 포함하지 않습니다.
  assert.deepEqual(
    summarize([
      { value: 2, status: 'done' },
      { value: -3, status: 'new' },
    ]),
    { total: 2, completed: 1, value: -1 },
  );
  // 목록이 비었을 때 오류/NaN 대신 모든 집계가 0이어야 합니다.
  assert.deepEqual(summarize([]), { total: 0, completed: 0, value: 0 });
});
test('음수 평균의 부호를 보존하고 막대 길이를 절댓값 비율로 계산한다', () => {
  // 준비: 평균 -4, 2, 없음. 최대 절댓값 4를 기준으로 막대는 100%, 50%, 0%입니다.
  // 막대 길이는 음수가 될 수 없지만 원래 평균 -4를 +4로 바꾸면 안 됩니다.
  // 아래 입력의 계산만 확인하며 실제 브라우저에서 막대를 그려본 검사는 아닙니다.
  assert.deepEqual(
    bars([{ mean: -4 }, { mean: 2 }, { mean: null }]).map((x) => [x.mean, x.width]),
    [
      [-4, 100],
      [2, 50],
      [null, 0],
    ],
  );
});
test('입력 오류의 필드 이름과 메시지를 표시하고 정보가 없으면 기본 문구를 쓴다', () => {
  // 서버 형식의 합성 오류를 준비합니다. body는 위치 분류이므로 빼고 title: required를 표시합니다.
  // HTTP 요청을 보내거나 실제 입력 제한을 검사하지 않고 오류 문장 변환 함수만 검사합니다.
  assert.equal(
    errorMessage({ detail: [{ loc: ['body', 'title'], msg: 'required' }] }),
    'title: required',
  );
  // 문자열 설명은 그대로, 설명이 없으면 호출자가 준 failed 문구를 사용해야 합니다.
  assert.equal(errorMessage({ detail: 'unavailable' }), 'unavailable');
  assert.equal(errorMessage(null, 'failed'), 'failed');
});
