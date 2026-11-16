"""Páginas del catálogo de productos (contracts/catalog-pages.md).

Formularios HTML clásicos con Post/Redirect/Get: si todo sale bien, 303 hacia el detalle; si
hay errores, se vuelve a mostrar el formulario con lo escrito (422 validación, 409 duplicado).
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from pydantic import BaseModel, ValidationError
from sqlmodel import Session

from app.db import get_session
from app.models.catalog import ProductInput
from app.services import catalog
from app.templating import templates

DUPLICATE_PRODUCT_MESSAGE = "Ya existe un producto activo con ese nombre"

router = APIRouter(prefix="/productos", tags=["catálogo"])

SessionDep = Annotated[Session, Depends(get_session)]


class ProductForm(BaseModel):
    """Lo que llega del formulario, tal cual se escribió: se valida después con ProductInput.

    Guardarlo sin validar permite volver a mostrarlo si hay errores (FR-012).
    """

    name: str = ""
    description: str = ""
    price: str = ""
    # Una casilla sin marcar no se envía en el formulario.
    tracks_inventory: bool = False


def _field_errors(error: ValidationError) -> dict[str, str]:
    """Un mensaje en español por campo, para mostrarlo junto a él."""
    return {str(item["loc"][0]): item["msg"] for item in error.errors()}


def _product_form(
    request: Request,
    form: dict[str, Any],
    errors: dict[str, str],
    status_code: int = status.HTTP_200_OK,
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "catalog/product_form.html",
        {"form": form, "errors": errors},
        status_code=status_code,
    )


@router.get("", response_class=HTMLResponse)
def list_products(request: Request, session: SessionDep) -> HTMLResponse:
    """Listado de productos activos, ordenado por nombre."""
    return templates.TemplateResponse(
        request, "catalog/list.html", {"products": catalog.list_products(session)}
    )


@router.get("/nuevo", response_class=HTMLResponse)
def new_product(request: Request) -> HTMLResponse:
    """Formulario vacío de producto."""
    return _product_form(request, ProductForm().model_dump(), {})


@router.post(
    "",
    response_class=HTMLResponse,
    status_code=status.HTTP_303_SEE_OTHER,
    responses={
        status.HTTP_409_CONFLICT: {"description": "Nombre activo repetido"},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"description": "Datos inválidos"},
    },
)
def create_product(
    request: Request, session: SessionDep, submitted: Annotated[ProductForm, Form()]
) -> Response:
    """Crea el producto y redirige a su detalle."""
    form = submitted.model_dump()
    try:
        data = ProductInput.model_validate(form)
    except ValidationError as error:
        return _product_form(
            request, form, _field_errors(error), status.HTTP_422_UNPROCESSABLE_CONTENT
        )
    try:
        product = catalog.create_product(session, data)
    except catalog.DuplicateProductError:
        return _product_form(
            request, form, {"name": DUPLICATE_PRODUCT_MESSAGE}, status.HTTP_409_CONFLICT
        )
    return RedirectResponse(f"/productos/{product.id}", status_code=status.HTTP_303_SEE_OTHER)


@router.get(
    "/{product_id}",
    response_class=HTMLResponse,
    responses={status.HTTP_404_NOT_FOUND: {"description": "El producto no existe"}},
)
def product_detail(request: Request, session: SessionDep, product_id: int) -> HTMLResponse:
    """Detalle del producto."""
    try:
        product = catalog.get_product(session, product_id)
    except catalog.ProductNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "El producto no existe") from error
    return templates.TemplateResponse(request, "catalog/detail.html", {"product": product})
