"""Authenticated, bounded HTTP bridge to the canonical evaluation engine.

Run behind a TLS reverse proxy; never expose the development bind publicly.
"""
from __future__ import annotations
import argparse
import hmac
import json
import os
import subprocess
import sys
import tempfile
import threading

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from . import __version__
from .interface import OPERATIONS

MAX_REQUEST = 1024 * 1024
MAX_RESPONSE = 16 * 1024 * 1024
WALL_SECONDS = 45

def _reject_constant(value):
    raise ValueError("Non-finite JSON")

def _child(body, timeout=WALL_SECONDS):
    # No service credential or proxy credentials in the evaluator process.
    # sys.executable resolves the installed package in the current venv.
    env = {"PATH":os.defpath,"LANG":"C.UTF-8","OPENBLAS_NUM_THREADS":"1",
           "OMP_NUM_THREADS":"1","MKL_NUM_THREADS":"1","NUMEXPR_NUM_THREADS":"1"}
    with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as inp:
        inp.write(body); inp.seek(0)
        try:
            result = subprocess.run([sys.executable,"-m","gridpass_flexibility.http_worker"],
                                    stdin=inp,stdout=output,stderr=subprocess.DEVNULL,
                                    env=env,timeout=timeout,check=False)
        except subprocess.TimeoutExpired:
            return 504, {"error":"evaluation_timeout"}
        if result.returncode:
            return 503, {"error":"evaluation_failed"}
        output.seek(0)
        raw=output.read(MAX_RESPONSE+1)
        if len(raw)>MAX_RESPONSE:
            return 503, {"error":"response_limit"}
        try:
            value=json.loads(raw,parse_constant=_reject_constant)
        except (ValueError,UnicodeError):
            return 503, {"error":"evaluation_failed"}
        if not isinstance(value,dict):
            return 503, {"error":"evaluation_failed"}
        if "result" in value:
            return 200,value
        return (422 if value.get("error")=="invalid_evaluation" else 503),value

def create_app(token: str, *, concurrency=1, timeout=WALL_SECONDS):
    if not isinstance(token,str) or len(token)<32 or not token.isascii():
        raise ValueError("Set a high-entropy ASCII service token of at least 32 characters")
    if type(concurrency) is not int or not 1<=concurrency<=2:
        raise ValueError("Concurrency must be 1 or 2")
    if not 0<timeout<=WALL_SECONDS:
        raise ValueError("Invalid wall timeout")
    expected=("Bearer "+token).encode("ascii")
    slots=threading.BoundedSemaphore(concurrency)
    app=FastAPI(docs_url=None,redoc_url=None,openapi_url=None)

    def response(status, body):
        return JSONResponse(body,status_code=status,headers={"Cache-Control":"no-store",
                            "X-Content-Type-Options":"nosniff"})

    @app.get("/health")
    async def health():
        return response(200,{"status":"ok","engine_version":__version__})

    @app.post("/evaluate")
    async def evaluate(request: Request):
        auth=request.headers.get("authorization","").encode("utf-8")
        if not hmac.compare_digest(auth,expected):
            return response(401,{"error":"unauthorized"})
        if request.headers.get("content-type","").split(";")[0].strip().lower()!="application/json":
            return response(415,{"error":"json_required"})
        if not slots.acquire(blocking=False):
            return response(429,{"error":"evaluation_busy"})
        try:
            length=request.headers.get("content-length")
            if length is not None:
                try:
                    if not 0<=int(length)<=MAX_REQUEST:
                        return response(413,{"error":"request_limit"})
                except ValueError:
                    return response(400,{"error":"invalid_length"})
            body=bytearray()
            # Limit both streamed bytes and the time a client may occupy a slot.
            import anyio
            try:
                with anyio.fail_after(5):
                    async for chunk in request.stream():
                        if len(body)+len(chunk)>MAX_REQUEST:
                            return response(413,{"error":"request_limit"})
                        body.extend(chunk)
            except TimeoutError:
                return response(408,{"error":"request_timeout"})
            try:
                obj=json.loads(body,parse_constant=_reject_constant)
                if (not isinstance(obj,dict) or set(obj)!={"operation","payload"}
                    or obj["operation"] not in OPERATIONS or not isinstance(obj["payload"],dict)):
                    raise ValueError("Invalid request")
            except (ValueError,TypeError,UnicodeError,RecursionError):
                return response(400,{"error":"invalid_request"})
            status,value=await run_in_threadpool(_child,bytes(body),timeout)
            return response(status,value)
        finally:
            slots.release()
    return app

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port",type=int,default=8766)
    parser.add_argument("--concurrency",type=int,default=1)
    args=parser.parse_args()
    token=os.environ.get("GRIDPASS_EVALUATION_TOKEN","")
    app=create_app(token,concurrency=args.concurrency)
    import uvicorn
    uvicorn.run(app,host="127.0.0.1",port=args.port,workers=1,limit_concurrency=12,
                timeout_keep_alive=3,access_log=False)

if __name__ == "__main__":
    main()
