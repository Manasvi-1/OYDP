import os
from contextlib import contextmanager
from uuid import UUID

import psycopg
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="OYDP Property Identity API", version="0.1.0")

class PropertyCreate(BaseModel):
    label: str = Field(min_length=1, max_length=200)
    jurisdiction: str = Field(min_length=1, max_length=100)

@contextmanager
def tenant_db(tenant_id: UUID):
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise RuntimeError("DATABASE_URL is required")
    with psycopg.connect(dsn) as conn:
        with conn.transaction():
            # Transaction-local scope is mandatory for pooled connections.
            conn.execute("SELECT set_config('app.tenant_id', %s, true)", (str(tenant_id),))
            yield conn

def disabled_identity():
    # Never trust a tenant header as authentication. An OIDC integration must
    # supply verified identity and membership before exposing these routes.
    raise HTTPException(status_code=503, detail="OIDC authentication not configured")

@app.get("/healthz")
def health():
    return {"status": "ok"}

@app.post("/v1/properties", status_code=201)
def create_property(payload: PropertyCreate):
    disabled_identity()

@app.get("/v1/properties/{property_id}")
def get_property(property_id: UUID):
    disabled_identity()
