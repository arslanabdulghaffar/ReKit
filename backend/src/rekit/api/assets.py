"""Authenticated bounded image transport; storage paths never come from clients."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from starlette.concurrency import run_in_threadpool

from rekit.api.workflow import IntakeOperator, Viewer
from rekit.auth import ActorKind
from rekit.catalog.models import Identifier
from rekit.evidence.assets import ImageAsset, ImageAssetStore, MAX_UPLOAD_BYTES, UploadResult
from rekit.evidence.models import AssertionSource


router = APIRouter(tags=["image evidence"])


def configured_assets(request: Request) -> ImageAssetStore:
    assets = request.app.state.assets
    if assets is None:
        raise HTTPException(status_code=503, detail="Image evidence storage is not configured.")
    return assets


AssetDependency = Annotated[ImageAssetStore, Depends(configured_assets)]


@router.post("/components/{component_id}/images", response_model=UploadResult, status_code=201)
async def upload_image(
    component_id: Identifier, return_id: Identifier, request: Request,
    response: Response, actor: IntakeOperator, assets: AssetDependency,
) -> UploadResult:
    """Accept one raw JPEG, PNG, or WebP body, never a client-selected filename."""
    if set(request.query_params) != {"return_id"} or len(request.query_params.getlist("return_id")) != 1:
        raise HTTPException(status_code=422, detail="Exactly one return_id query parameter is required.")
    if request.headers.get("content-encoding", "identity").lower() != "identity":
        raise HTTPException(status_code=415, detail="Encoded upload bodies are not supported.")
    content_type = request.headers.get("content-type", "").lower()
    if content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise HTTPException(status_code=415, detail="Use image/jpeg, image/png, or image/webp.")
    lengths = request.headers.getlist("content-length")
    if lengths:
        if len(lengths) != 1 or not lengths[0].isascii() or not lengths[0].isdigit():
            raise HTTPException(status_code=400, detail="Invalid upload length.")
        if len(lengths[0]) > 10 or int(lengths[0]) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="Images must be at most 10 MiB.")
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="Images must be at most 10 MiB.")
        body.extend(chunk)
    source = AssertionSource.OPERATOR if actor.kind == ActorKind.HUMAN else AssertionSource.IMPORT
    result = await run_in_threadpool(
        assets.upload, component_id, return_id, bytes(body), content_type, actor.actor_id, source,
    )
    if result.duplicate:
        response.status_code = 200
    return result


@router.get("/components/{component_id}/images", response_model=tuple[ImageAsset, ...])
def component_images(component_id: Identifier, actor: Viewer, assets: AssetDependency) -> tuple[ImageAsset, ...]:
    return assets.list_assets(component_id)


@router.get("/assets/{asset_id}", response_model=ImageAsset)
def asset_metadata(asset_id: Identifier, actor: Viewer, assets: AssetDependency) -> ImageAsset:
    return assets.metadata(asset_id)


@router.get("/assets/{asset_id}/content")
def asset_content(asset_id: Identifier, actor: Viewer, assets: AssetDependency) -> Response:
    asset, content = assets.read(asset_id)
    return Response(content=content, media_type=asset.media_type, headers={
        "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": "default-src 'none'; sandbox",
    })
