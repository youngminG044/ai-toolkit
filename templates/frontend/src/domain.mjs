// 네트워크/화면 변경 없이 입력을 계산하는 함수들입니다. App.tsx에서 호출하고
// domain.test.mjs에서 작은 고정 입력의 기대값과 실제 결과를 비교합니다.

/** 전달된 목록만 집계합니다. 서버 전체 건수와 다를 수 있으므로 total과 혼동하지 않습니다. */
export function summarize(items) {
  return {
    total: items.length,
    // filter는 완료 상태만 남깁니다. length는 남은 항목의 수입니다.
    completed: items.filter((item) => item.status === 'done').length,
    // reduce는 누적값 sum에 각 수치를 더합니다. 시작값 0이므로 빈 목록의 합도 0입니다.
    value: items.reduce((sum, item) => sum + item.value, 0),
  };
}

/** 평균 절댓값을 0~100% 막대 길이로 변환합니다. 값의 부호/정확한 크기는 표에서 읽습니다. */
export function bars(groups) {
  // ?? 0은 평균이 없을 때 0으로 보는 표시 규칙입니다. 분모를 최소 1로 두어 0 나누기를 피합니다.
  // 최대 절댓값이 1보다 작으면 그 최댓값도 100%가 되지 않는 현재 표시 방식을 유지합니다.
  const max = Math.max(1, ...groups.map((group) => Math.abs(group.mean ?? 0)));
  return groups.map((group) => ({ ...group, width: (Math.abs(group.mean ?? 0) / max) * 100 }));
}

/** 서버 오류에서 읽을 문장을 고릅니다. 문자열/입력 검증 목록이 아니면 기본 문구를 사용합니다. */
export function errorMessage(payload, fallback = '요청을 처리하지 못했습니다.') {
  if (typeof payload?.detail === 'string') return payload.detail;
  if (Array.isArray(payload?.detail))
    return (
      payload.detail
        // loc의 첫 값(body/query 등)을 제외하고 실제 입력 필드 이름을 점으로 연결합니다.
        .map((item) => `${item.loc?.slice(1).join('.') || '입력'}: ${item.msg}`)
        .join(' / ')
    );
  return fallback;
}
