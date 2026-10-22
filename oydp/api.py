"""Small authenticated property slice; no demo-token or in-memory production mode."""
import os
from pathlib import Path
from typing import Annotated
from uuid import UUID
from datetime import datetime
import jwt
from fastapi import FastAPI, Depends, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ConfigDict, Field
from oydp.auth import TokenVerifier
from oydp.repository import Repository, Unavailable


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class PropertyInput(StrictModel):
    name: str = Field(min_length=1, max_length=200)
    jurisdiction: str = Field(default='unresolved', min_length=1, max_length=200)


class ClaimInput(StrictModel):
    statement: str = Field(min_length=1, max_length=10000)


class PropertyOutput(PropertyInput):
    id: UUID
    created_at: datetime


class ClaimOutput(ClaimInput):
    id: UUID
    property_id: UUID
    kind: str
    recorded_at: datetime


def create_app(repository, verifier):
    app = FastAPI(title='OYDP Property Foundation', version='0.2.0', docs_url=None, redoc_url=None)
    bearer = HTTPBearer(auto_error=False)

    def identity(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]):
        if credentials is None:
            raise HTTPException(401, 'Authentication required', headers={'WWW-Authenticate': 'Bearer'})
        try:
            return verifier.verify(credentials.credentials)
        except (jwt.PyJWTError, ValueError, TypeError, KeyError):
            raise HTTPException(401, 'Invalid token', headers={'WWW-Authenticate': 'Bearer'}) from None

    def context(actor=Depends(identity), x_tenant_id: UUID = Header()):
        return x_tenant_id, actor

    def sensitive(ctx=Depends(context)):
        if not ctx[1].mfa:
            raise HTTPException(403, 'MFA required')
        return ctx

    @app.middleware('http')
    async def response_privacy(request: Request, call_next):
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    @app.exception_handler(Unavailable)
    async def unavailable(request, exc):
        return JSONResponse(status_code=404, content={'detail': 'Resource unavailable'})

    @app.exception_handler(RequestValidationError)
    async def invalid_input(request, exc):
        # Never echo raw input, bearer tokens or private statements into error responses.
        return JSONResponse(status_code=422, content={'detail': 'Invalid request'})

    @app.get('/health/live')
    def health():
        return {'status': 'alive'}

    @app.post('/v1/properties', response_model=PropertyOutput, status_code=201)
    def create(data: PropertyInput, ctx=Depends(sensitive)):
        return repository.create(*ctx, data)

    @app.get('/v1/properties', response_model=list[PropertyOutput])
    def list_properties(ctx=Depends(context), limit: int = Query(25, ge=1, le=100),
                        offset: int = Query(0, ge=0, le=10000)):
        return repository.list(*ctx, limit, offset)

    @app.get('/v1/properties/{property_id}', response_model=PropertyOutput)
    def get_property(property_id: UUID, ctx=Depends(context)):
        return repository.get(*ctx, property_id)

    @app.post('/v1/properties/{property_id}/claims', response_model=ClaimOutput, status_code=201)
    def record_claim(property_id: UUID, data: ClaimInput, ctx=Depends(sensitive)):
        return repository.claim(*ctx, property_id, data)

    return app


def app_from_env():
    # Startup fails if authentication/database configuration is absent. No default credential.
    verifier = TokenVerifier(Path(os.environ['OYDP_JWT_PUBLIC_KEY_FILE']).read_text(),
                             os.environ['OYDP_JWT_ISSUER'], os.environ['OYDP_JWT_AUDIENCE'])
    return create_app(Repository(os.environ['OYDP_DATABASE_URL']), verifier)
