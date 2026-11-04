import { errorMessage } from './domain.mjs';

/**
 * App.tsx가 사용하는 HTTP 통신 공통 함수입니다.
 * path='/items', method='POST', body={...}이면 /api/items에 JSON을 보냅니다.
 * T는 호출자가 기대하는 응답의 TypeScript 타입으로, 실제 서버 응답을 검사하지는 않습니다.
 * 성공하면 응답 값을 반환하고 실패하면 Error를 던져 App.tsx의 perform이 표시합니다.
 * 이 함수는 백그라운드 작업 큐나 재시도/재시작 복구를 구현하지 않습니다.
 */
export async function api<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  // fetch는 페이지를 이동하지 않고 서버에 요청합니다. await 동안 다른 UI 이벤트는 처리할 수 있습니다.
  // 단, CPU를 오래 쓰는 동기 계산을 async 함수에 넣는다고 화면이 덜 멈추는 것은 아닙니다.
  const response = await fetch(`/api${path}`, {
    method,
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  // 204는 응답 본문이 없는 삭제 성공 등입니다. JSON을 읽으려 하지 않고 끝냅니다.
  if (response.status === 204) return undefined as T;
  const payload = await response.json().catch(() => null);
  // fetch는 HTTP 4xx/5xx 자체로 예외를 던지지 않으므로 여기서 성공 여부를 따로 검사합니다.
  if (!response.ok) throw new Error(errorMessage(payload, `요청 실패 (${response.status})`));
  return payload as T;
}
