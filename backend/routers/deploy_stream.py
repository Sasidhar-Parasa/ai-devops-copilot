"""
SSE streaming endpoint for real-time deployment progress.
GET /api/deploy/stream?repo_url=...&app_name=...
"""
import logging
from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/deploy/stream")
async def deploy_stream(
    repo_url: str  = Query(..., description="GitHub repository URL"),
    app_name: str  = Query("app", description="Application name"),
    version:  str  = Query("latest", description="Version tag"),
):
    """
    Server-Sent Events endpoint for real-time deployment logs.
    Frontend connects with EventSource and receives events as they happen.
    """
    from services.deploy_service import stream_deploy_pipeline

    logger.info("SSE deploy stream: repo=%s app=%s", repo_url, app_name)

    async def event_generator():
        try:
            async for chunk in stream_deploy_pipeline(repo_url, app_name, version):
                yield chunk
        except Exception as exc:  # noqa: BLE001
            import json
            from datetime import datetime
            logger.exception("Stream error: %s", exc)
            yield f"data: {json.dumps({'stage': 'done', 'status': 'failed', 'error': str(exc), 'timestamp': datetime.utcnow().isoformat()})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":               "no-cache",
            "X-Accel-Buffering":           "no",
            "Access-Control-Allow-Origin": "*",
        },
    )

