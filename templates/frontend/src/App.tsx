import { useEffect, useState, type FormEvent } from 'react';
import { api } from './api';
import { summarize, bars } from './domain.mjs';

// 이 파일은 업무 기록·CSV 분석·문서 탐색 화면을 묶습니다.
// 읽는 순서: 화면의 onSubmit/onClick → 아래 submit/perform → api.ts → 서버 app/main.py.
// URL 라우터는 사용하지 않고 tab이라는 화면 상태로 같은 페이지의 내용만 바꿉니다.
type Item = {
  id: string;
  title: string;
  category: string;
  value: number;
  status: 'new' | 'active' | 'done';
};
type Document = { id: string; name: string; created_at: string };
type Citation = {
  id: string;
  source: string;
  text: string;
  line_start: number;
  line_end: number;
  score: number;
};
type Answer = { answer: string; abstained: boolean; mode: string; citations: Citation[] };
type Profile = {
  rows: number;
  exact_duplicates: number;
  columns: {
    name: string;
    kind: string;
    missing: number;
    unique: number;
    mean?: number;
    min?: number;
    max?: number;
  }[];
  groups?: { group: string; count: number; sum: number; mean: number | null }[];
};
const labels = { new: '새 항목', active: '진행 중', done: '완료' };
const initialItem = { title: '', category: '일반', value: '0', status: 'new' as Item['status'] };
const message = (error: unknown) =>
  error instanceof Error ? error.message : '처리 중 오류가 발생했습니다.';
const number = (value: number) => value.toLocaleString('ko-KR', { maximumFractionDigits: 3 });

export default function App() {
  // useState는 화면이 기억할 값과 그 값을 바꾸는 함수를 한 쌍으로 만듭니다.
  // 예: setTab('data')를 부르면 새 페이지로 이동하지 않고 CSV 화면을 다시 그립니다.
  const [tab, setTab] = useState('records');
  const [items, setItems] = useState<Item[]>([]);
  const [total, setTotal] = useState(0);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [item, setItem] = useState(initialItem);
  const [csv, setCsv] = useState('');
  const [group, setGroup] = useState('');
  const [valueColumn, setValueColumn] = useState('');
  const [profile, setProfile] = useState<Profile | null>(null);
  const [documentName, setDocumentName] = useState('');
  const [documentText, setDocumentText] = useState('');
  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [loading, setLoading] = useState(true);
  const refreshItems = async () => {
    const result = await api<{ items: Item[]; total: number }>('/items?limit=1000');
    setItems(result.items);
    setTotal(result.total);
  };
  const refreshDocuments = async () => setDocuments(await api<Document[]>('/documents'));
  useEffect(() => {
    // 첫 표시 때 기록/문서 목록을 함께 요청합니다. Promise.all은 둘 다 성공해야
    // 다음 단계로 갑니다. 한 요청 실패 시 여기서는 초기 로딩 전체를 오류로 표시합니다.
    // active는 이미 사라진 화면에 결과를 반영하지 않기 위한 값이며 요청 취소는 아닙니다.
    let active = true;
    Promise.all([
      api<{ items: Item[]; total: number }>('/items?limit=1000'),
      api<Document[]>('/documents'),
    ])
      .then(([records, docs]) => {
        if (active) {
          setItems(records.items);
          setTotal(records.total);
          setDocuments(docs);
        }
      })
      .catch((e) => {
        if (active) setError(message(e));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);
  async function perform(action: () => Promise<void>) {
    // 비동기 작업 동안 로딩/오류 상태를 관리합니다. await는 통신 결과를 기다립니다.
    // busy는 이 화면의 중복 조작을 줄이는 장치입니다. 서버 잠금·작업 큐가 아니므로
    // 다른 사용자/탭의 요청이나 서버 재시작 중 작업 복구까지 보장하지는 않습니다.
    if (busy) return;
    setBusy(true);
    setError('');
    setNotice('');
    try {
      await action();
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  }
  const submit = (event: FormEvent, action: () => Promise<void>) => {
    // 브라우저 기본 폼 제출(페이지 이동/새로고침)을 막고 같은 화면에서 API를 호출합니다.
    event.preventDefault();
    void perform(action);
  };
  const stats = summarize(items);

  return (
    <div className="shell">
      <aside className="sidebar">
        <button
          type="button"
          className="brand"
          onClick={() => setTab('records')}
          aria-label="Workspace 홈"
        >
          <span className="brand-icon">W</span> Workspace
        </button>
        <p className="eyebrow">WORKBENCH / 01</p>
        <nav aria-label="주요 메뉴">
          {[
            ['records', '01', '업무 기록'],
            ['data', '02', '데이터 분석'],
            ['knowledge', '03', '문서 탐색'],
          ].map(([key, index, label]) => (
            <button
              key={key}
              aria-current={tab === key ? 'page' : undefined}
              onClick={() => {
                setTab(key);
                setError('');
                setNotice('');
              }}
            >
              <span>{index}</span>
              {label}
              <span className="arrow">↗</span>
            </button>
          ))}
        </nav>
        <div className="sidebar-note">
          <span className="dot" /> 작업 공간
          <br />
          <small>입력한 기록과 문서는 서버에 저장됩니다.</small>
        </div>
      </aside>
      <main>
        <header className="topbar">
          <span>
            WORKSPACE / {tab === 'records' ? 'RECORDS' : tab === 'data' ? 'ANALYTICS' : 'KNOWLEDGE'}
          </span>
          {/* 개발용 API 주소는 KIT_GUIDE.md에서 안내합니다. 제품 화면에서 새 탭을 열지 않습니다. */}
        </header>
        <section className="heading">
          <p className="eyebrow">MAKE YOUR WORK VISIBLE</p>
          <h1>
            {tab === 'records'
              ? '업무를 한눈에.'
              : tab === 'data'
                ? '숫자에서 시작하는 이해.'
                : '문서에 근거한 답변.'}
          </h1>
          <p>
            {tab === 'records'
              ? '기록하고, 진행 상태를 바꾸고, 결과를 확인하세요.'
              : tab === 'data'
                ? 'CSV의 결측·중복과 그룹별 수치를 확인하세요.'
                : '문서를 등록하고 질문에 관련된 원문과 출처를 찾아보세요.'}
          </p>
        </section>
        {error && (
          <div className="alert error" role="alert">
            {error}{' '}
            <button
              disabled={busy}
              onClick={() =>
                void perform(async () => {
                  await Promise.all([refreshItems(), refreshDocuments()]);
                  setNotice('다시 연결했습니다.');
                })
              }
            >
              연결 재시도
            </button>
          </div>
        )}
        {notice && (
          <div className="alert" role="status">
            {notice}
          </div>
        )}
        {busy && (
          <p role="status" className="muted">
            처리 중…
          </p>
        )}
        {tab === 'records' && (
          <>
            <div className="metrics">
              {[
                [
                  '조회된 기록',
                  number(stats.total),
                  total > items.length ? `전체 ${number(total)}개 중 최근 1,000개` : '전체 기록',
                ],
                ['완료', number(stats.completed), '조회된 기록 기준'],
                ['값 합계', number(stats.value), '조회된 기록 · 입력 단위 기준'],
              ].map(([label, value, note]) => (
                <article key={label}>
                  <p>{label}</p>
                  <strong>{value}</strong>
                  <small>{note}</small>
                </article>
              ))}
            </div>
            <div className="section-title">
              <h2>기록 목록</h2>
              <span>{number(total)} ITEMS</span>
            </div>
            <form
              className="panel item-form"
              onSubmit={(e) =>
                submit(e, async () => {
                  await api('/items', 'POST', { ...item, value: Number(item.value) });
                  setItem(initialItem);
                  await refreshItems();
                  setNotice('기록을 저장했습니다.');
                })
              }
            >
              <label>
                제목
                <input
                  required
                  maxLength={150}
                  value={item.title}
                  onChange={(e) => setItem({ ...item, title: e.target.value })}
                  placeholder="기록할 업무"
                />
              </label>
              <label>
                분류
                <input
                  required
                  maxLength={60}
                  value={item.category}
                  onChange={(e) => setItem({ ...item, category: e.target.value })}
                />
              </label>
              <label>
                값
                <input
                  type="number"
                  step="any"
                  required
                  value={item.value}
                  onChange={(e) => setItem({ ...item, value: e.target.value })}
                />
              </label>
              <button className="primary" disabled={busy || loading}>
                기록 추가 +
              </button>
            </form>
            <div className="panel table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>제목</th>
                    <th>분류</th>
                    <th className="numeric">값</th>
                    <th>상태</th>
                    <th>
                      <span className="sr-only">작업</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((row) => (
                    <tr key={row.id}>
                      <td className="title-cell">{row.title}</td>
                      <td>{row.category}</td>
                      <td className="numeric">{number(row.value)}</td>
                      <td>
                        <select
                          aria-label={`${row.title} 상태`}
                          disabled={busy}
                          value={row.status}
                          onChange={(e) => {
                            const status = e.target.value;
                            void perform(async () => {
                              await api(`/items/${row.id}`, 'PUT', {
                                title: row.title,
                                category: row.category,
                                value: row.value,
                                status,
                              });
                              await refreshItems();
                            });
                          }}
                        >
                          {Object.entries(labels).map(([key, label]) => (
                            <option key={key} value={key}>
                              {label}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td>
                        <button
                          className="text-button"
                          disabled={busy}
                          aria-label={`${row.title} 삭제`}
                          onClick={() =>
                            void perform(async () => {
                              await api(`/items/${row.id}`, 'DELETE');
                              await refreshItems();
                              setNotice('기록을 삭제했습니다.');
                            })
                          }
                        >
                          삭제
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {(loading || !items.length) && (
                <p className="empty">
                  {loading
                    ? '기록을 불러오는 중입니다.'
                    : '아직 기록이 없습니다. 첫 업무를 추가해 보세요.'}
                </p>
              )}
            </div>
          </>
        )}
        {tab === 'data' && (
          <div className="stack">
            <form
              className="panel padded stack"
              onSubmit={(e) =>
                submit(e, async () => {
                  setProfile(
                    await api<Profile>('/data/profile', 'POST', {
                      csv_text: csv,
                      group_by: group || null,
                      value_column: valueColumn || null,
                    }),
                  );
                  setNotice('분석을 완료했습니다.');
                })
              }
            >
              <div className="section-title">
                <h2>CSV 입력</h2>
                <span>최대 500만 자</span>
              </div>
              {/* 파일 선택창을 띄우지 않고 페이지 안에서 텍스트를 받습니다. */}
              <label>
                CSV 텍스트
                <textarea
                  required
                  maxLength={5000000}
                  rows={5}
                  value={csv}
                  onChange={(e) => {
                    setCsv(e.target.value);
                    setProfile(null);
                  }}
                  placeholder={'team,value\nA,12\nB,8\nA,6'}
                />
              </label>
              <div className="form-row">
                <label>
                  그룹 열 (선택)
                  <input
                    value={group}
                    onChange={(e) => setGroup(e.target.value)}
                    placeholder="team"
                  />
                </label>
                <label>
                  수치 열 (그룹 집계 시 필수)
                  <input
                    value={valueColumn}
                    onChange={(e) => setValueColumn(e.target.value)}
                    placeholder="value"
                  />
                </label>
                <button className="primary" disabled={busy || !csv.trim()}>
                  분석 실행 ↗
                </button>
              </div>
            </form>
            {profile && (
              <>
                <div className="metrics">
                  <article>
                    <p>행 수</p>
                    <strong>{number(profile.rows)}</strong>
                    <small>헤더 제외</small>
                  </article>
                  <article>
                    <p>열 수</p>
                    <strong>{profile.columns.length}</strong>
                    <small>파싱된 열</small>
                  </article>
                  <article>
                    <p>중복 행</p>
                    <strong>{number(profile.exact_duplicates)}</strong>
                    <small>모든 열이 같은 추가 행</small>
                  </article>
                </div>
                <div className="panel table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>열</th>
                        <th>종류</th>
                        <th>결측</th>
                        <th>고유 값</th>
                        <th>평균</th>
                        <th>최솟값 / 최댓값</th>
                      </tr>
                    </thead>
                    <tbody>
                      {profile.columns.map((column) => (
                        <tr key={column.name}>
                          <td className="title-cell">{column.name}</td>
                          <td>{column.kind}</td>
                          <td>{column.missing}</td>
                          <td>{column.unique}</td>
                          <td>{column.mean == null ? '—' : number(column.mean)}</td>
                          <td>
                            {column.min == null
                              ? '—'
                              : `${number(column.min)} / ${number(column.max!)}`}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {profile.groups && (
                  <div className="panel padded">
                    <h2>그룹별 평균</h2>
                    <p className="muted">
                      유효한 수치만 집계 · 단위는 입력 데이터 기준 · 막대는 절댓값 크기
                    </p>
                    {bars(profile.groups).map((row) => (
                      <div className="bar-row" key={row.group}>
                        <span>{row.group || '(빈 값)'}</span>
                        <div className="bar-track">
                          <div style={{ width: `${row.width}%` }} />
                        </div>
                        <strong>{row.mean == null ? '—' : number(row.mean)}</strong>
                        <small>n={row.count}</small>
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}
          </div>
        )}
        {tab === 'knowledge' && (
          <div className="knowledge-grid">
            <section className="panel padded stack">
              <h2>근거 문서</h2>
              <p className="muted">UTF-8 텍스트/Markdown · 문서당 10만 자 · 최대 50개</p>
              <form
                className="stack"
                onSubmit={(e) =>
                  submit(e, async () => {
                    await api('/documents', 'POST', { name: documentName, text: documentText });
                    setDocumentName('');
                    setDocumentText('');
                    setAnswer(null);
                    await refreshDocuments();
                    setNotice('문서를 등록했습니다.');
                  })
                }
              >
                {/* 문서 이름과 본문도 같은 페이지에서 입력합니다. 자동 파일/권한 창은 열지 않습니다. */}
                <label>
                  문서 이름
                  <input
                    required
                    maxLength={150}
                    value={documentName}
                    onChange={(e) => setDocumentName(e.target.value)}
                  />
                </label>
                <label>
                  본문
                  <textarea
                    required
                    rows={7}
                    maxLength={100000}
                    value={documentText}
                    onChange={(e) => setDocumentText(e.target.value)}
                  />
                </label>
                <button className="primary" disabled={busy}>
                  문서 등록 +
                </button>
              </form>
              <ul className="document-list">
                {documents.map((doc) => (
                  <li key={doc.id}>
                    <span>{doc.name}</span>
                    <button
                      className="text-button"
                      disabled={busy}
                      aria-label={`${doc.name} 문서 삭제`}
                      onClick={() =>
                        void perform(async () => {
                          await api(`/documents/${doc.id}`, 'DELETE');
                          setAnswer(null);
                          await refreshDocuments();
                        })
                      }
                    >
                      삭제
                    </button>
                  </li>
                ))}
              </ul>
              {!documents.length && <p className="muted">등록된 문서가 없습니다.</p>}
            </section>
            <section className="panel padded stack">
              <div className="section-title">
                <h2>문서에 질문하기</h2>
                <span>출처 확인</span>
              </div>
              <p className="muted">
                기본 모드는 검색된 원문을 발췌합니다. 답변은 등록 문서의 사실 여부를 보장하지
                않으므로 출처를 직접 확인하세요.
              </p>
              <form
                className="stack"
                onSubmit={(e) =>
                  submit(e, async () => {
                    setAnswer(null);
                    setAnswer(await api<Answer>('/rag/answer', 'POST', { question, k: 3 }));
                  })
                }
              >
                <label>
                  질문
                  <textarea
                    required
                    rows={3}
                    maxLength={2000}
                    value={question}
                    onChange={(e) => setQuestion(e.target.value)}
                    placeholder="문서에서 확인할 내용을 입력하세요."
                  />
                </label>
                <button className="primary" disabled={busy || !documents.length}>
                  근거 찾기 ↗
                </button>
              </form>
              {answer && (
                <div aria-live="polite">
                  <p className="eyebrow">
                    {answer.abstained
                      ? '근거 없음'
                      : answer.mode === 'extractive'
                        ? '원문 발췌'
                        : '연결된 생성기 답변'}
                  </p>
                  <p className="answer">{answer.answer}</p>
                  {answer.citations.map((citation) => (
                    <details key={citation.id}>
                      <summary>
                        {citation.source} · {citation.line_start}–{citation.line_end}행
                      </summary>
                      <pre>{citation.text}</pre>
                    </details>
                  ))}
                </div>
              )}
            </section>
          </div>
        )}
        <footer>
          Workspace <span>기록 → 분석 → 근거 확인</span>
        </footer>
      </main>
    </div>
  );
}
