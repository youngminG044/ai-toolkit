"""HTTP 요청을 데이터 검증·저장·분석/검색으로 연결하는 서버 진입점입니다.

읽는 순서: 입력 모델 → create_app → @app.<메서드>로 등록한 경로 → database/analysis/rag 함수.
이 뼈대는 단일 사용자용이며 인증·영속 작업 큐·무거운 계산의 별도 워커는 포함하지 않습니다.
"""

from contextlib import asynccontextmanager
from html import escape
from pathlib import Path
from typing import Literal
import os

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from ai.rag import answer
from data.analysis import profile
from .database import Database


class ItemInput(BaseModel):
    # HTTP JSON을 이 타입으로 검사합니다. 잘못된 필드·공백 제목·NaN/무한대는
    # 처리 함수에 들어가기 전에 422 응답이 됩니다. 업무별 추가 규칙은 별도로 구현합니다.
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False, str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=150)
    category: str = Field(default='일반', min_length=1, max_length=60)
    value: float = 0
    status: Literal['new', 'active', 'done'] = 'new'


class DocumentInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=150)
    text: str = Field(min_length=1, max_length=100_000)


class Question(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    question: str = Field(min_length=1, max_length=2000)
    k: int = Field(default=3, ge=1, le=10)


class DataInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    csv_text: str = Field(min_length=1, max_length=5_000_000)
    group_by: str | None = None
    value_column: str | None = None


def create_app(database_path=None, static_dir=None, generator=None, enable_api_docs=None):
    """서버와 저장 객체를 묶습니다. 테스트는 임시 DB 경로를 주어 실제 데이터를 보존합니다.

    database_path는 SQLite 파일, static_dir는 빌드된 화면 위치입니다.
    generator는 선택형 AI 생성 함수이며 기본 검색/발췌에는 외부 키가 필요 없습니다.
    DB 초기화는 아래 lifespan 시작 때 실행하며, yield는 서버 종료까지 제어를 넘깁니다.
    asynccontextmanager는 수명 관리 문법으로 백그라운드 작업 저장/복구 기능이 아닙니다.
    """
    db_path = Path(database_path) if database_path else Path(os.getenv('DATA_DIR', '.local/app')) / 'app.sqlite3'
    database = Database(db_path)

    @asynccontextmanager
    async def lifespan(application):
        database.initialize()
        yield

    docs_enabled = (os.getenv('ENABLE_API_DOCS', 'true').lower() in {'true', '1', 'yes'}
                    if enable_api_docs is None else enable_api_docs)
    app = FastAPI(
        title='Workspace API', version='1.0.0', lifespan=lifespan,
        description='단일 사용자용 개발 API. 요청·응답 계약과 실제 업무 검증은 구분합니다.',
        docs_url='/docs' if docs_enabled else None,
        redoc_url='/redoc' if docs_enabled else None,
        openapi_url='/openapi.json' if docs_enabled else None,
    )
    app.state.database = database

    @app.get('/health', tags=['상태'], summary='프로세스 응답 확인')
    def liveness():
        """프로세스가 응답하면 status=ok를 반환합니다. DB·모델 준비나 업무 정확성은 검사하지 않습니다."""
        return {'status': 'ok'}

    @app.get('/api/health', tags=['상태'], summary='기존 클라이언트용 상태·구성 정보')
    def health():
        """프로세스 상태와 선택된 저장/검색 방식을 반환합니다. 외부 의존성의 정상 여부를 보장하지 않습니다."""
        return {'status': 'ok', 'storage': 'sqlite', 'rag_mode': 'extractive' if generator is None else 'provided-generator'}

    @app.get('/api/items', tags=['기록'], summary='기록 목록과 전체 건수 조회')
    def list_items(limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0)):
        """화면의 목록 요청을 DB로 전달합니다. limit은 읽을 개수, offset은 건너뛸 개수입니다."""
        return database.items(limit, offset)

    @app.post('/api/items', status_code=201, tags=['기록'], summary='검증한 기록을 SQLite에 저장')
    def create_item(item: ItemInput):
        """검증을 통과한 입력을 사전으로 바꿔 저장하고 ID가 포함된 결과를 화면에 돌려줍니다."""
        return database.create_item(item.model_dump())

    @app.put('/api/items/{identifier}', tags=['기록'], summary='ID로 기록 전체 갱신', responses={404: {'description': '해당 ID 없음'}})
    def update_item(identifier: str, item: ItemInput):
        """URL의 ID에 해당하는 기록을 교체합니다. 없는 ID면 성공처럼 보이지 않도록 404를 반환합니다."""
        result = database.update_item(identifier, item.model_dump())
        if result is None:
            raise HTTPException(404, 'item not found')
        return result

    @app.delete('/api/items/{identifier}', status_code=204, tags=['기록'], summary='ID로 기록 삭제', responses={404: {'description': '해당 ID 없음'}})
    def delete_item(identifier: str):
        """기록 삭제 후 본문 없는 204를 반환합니다. api.ts는 이 응답의 JSON을 읽지 않습니다."""
        if not database.delete('items', identifier):
            raise HTTPException(404, 'item not found')
        return Response(status_code=204)

    @app.post('/api/data/profile', tags=['데이터'], summary='CSV 품질·그룹 집계', responses={422: {'description': '잘못된 입력 또는 CSV'}})
    def analyze(data: DataInput):
        """csv_text를 파싱하고 요청한 그룹·값 열을 집계합니다. 원본 CSV를 DB에 저장하지 않습니다."""
        try:
            return profile(data.csv_text, data.group_by, data.value_column)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error

    @app.get('/api/documents', tags=['문서'], summary='저장한 문서의 메타데이터 조회')
    def list_documents():
        """문서 목록 화면에는 메타데이터만 보냅니다. 전체 본문은 검색 처리에서 따로 읽습니다."""
        return database.documents()

    @app.post('/api/documents', status_code=201, tags=['문서'], summary='검색할 문서 저장', responses={409: {'description': '문서 충돌'}})
    def add_document(document: DocumentInput):
        """본문/이름 검증 뒤 DB에 저장합니다. 저장 정책과 충돌하면 409로 표시합니다."""
        try:
            return database.add_document(document.name, document.text)
        except ValueError as error:
            raise HTTPException(409, str(error)) from error

    @app.delete('/api/documents/{identifier}', status_code=204, tags=['문서'], summary='ID로 문서 삭제', responses={404: {'description': '해당 ID 없음'}})
    def delete_document(identifier: str):
        """ID가 있는 문서만 삭제하고, 없는 문서는 404로 구분합니다."""
        if not database.delete('documents', identifier):
            raise HTTPException(404, 'document not found')
        return Response(status_code=204)

    @app.post('/api/rag/answer', tags=['문서'], summary='저장 문서 검색·근거 인용', responses={503: {'description': '연결한 생성기 실패'}})
    def question(question: Question):
        """기본은 BM25 검색과 원문 발췌입니다. 근거 부족 시 abstained=true이며, 생성기는 별도 주입한 경우에만 사용합니다."""
        documents = database.documents(include_text=True)
        try:
            return answer(question.question, [(d['name'], d['text']) for d in documents], question.k, generator)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        except Exception as error:
            raise HTTPException(503, 'answer generation failed') from error

    if docs_enabled:
        @app.get('/api', response_class=HTMLResponse, tags=['안내'], summary='API 목록·문서 링크')
        def api_index():
            """현재 OpenAPI 계약에서 메서드·경로·목적·응답 코드를 읽어 보여주는 외부 리소스 없는 안내입니다."""
            rows = []
            for path, operations in sorted(app.openapi()['paths'].items()):
                for method, operation in operations.items():
                    if method not in {'get', 'post', 'put', 'patch', 'delete', 'head', 'options', 'trace'}:
                        continue
                    purpose = escape(operation.get('summary', ''))
                    description = escape(operation.get('description', ''))
                    codes = escape(', '.join(operation.get('responses', {})))
                    rows.append(f'<tr><td>{method.upper()}</td><td><code>{escape(path)}</code></td>'
                                f'<td>{purpose}<br><small>{description}</small></td><td>{codes}</td></tr>')
            return HTMLResponse(
                '<!doctype html><html lang="ko"><meta charset="utf-8">'
                '<meta name="viewport" content="width=device-width, initial-scale=1">'
                '<title>API 안내</title><style>body{font:16px system-ui;max-width:1100px;margin:2rem auto;padding:0 1rem}'
                'table{border-collapse:collapse;width:100%}td,th{text-align:left;padding:.6rem;border:1px solid #ccc}'
                'small{color:#444}code{overflow-wrap:anywhere}</style><body><h1>API 안내</h1>'
                '<p><a href="health">상태 확인</a> · <a href="docs">Swagger UI</a> · '
                '<a href="redoc">ReDoc</a> · <a href="openapi.json">OpenAPI JSON</a></p>'
                '<p>현재 라우트 계약에서 만든 목록입니다. 요청·응답 필드는 OpenAPI 또는 Swagger UI에서 확인하세요. '
                '이 목록은 읽기 전용이며 Swagger UI의 실행 기능은 실제 데이터를 변경할 수 있습니다.</p>'
                '<p>/health는 프로세스 응답만 확인합니다. 업무 기능과 데이터 정확성은 별도로 검증하세요.</p>'
                '<table><thead><tr><th>메서드</th><th>경로</th><th>목적</th><th>응답 코드</th></tr></thead><tbody>'
                + ''.join(rows) + '</tbody></table></body></html>'
            )

    static = Path(static_dir or os.getenv('STATIC_DIR', 'frontend/dist'))
    if static.is_dir():
        app.mount('/', StaticFiles(directory=static, html=True), name='frontend')
    return app


app = create_app()
