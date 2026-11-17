
from fastapi import (
    APIRouter,
    Request,
    Depends,
    Form
)

from fastapi.responses import HTMLResponse

from fastapi.templating import Jinja2Templates

from sqlalchemy.orm import Session

from app.core.database import get_db

from app.services.review_service import ReviewService


router = APIRouter()

templates = Jinja2Templates(
    directory="app/templates"
)


@router.get("/", response_class=HTMLResponse)
def index(request: Request):

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "result": None
        }
    )


@router.post("/analyze", response_class=HTMLResponse)
def analyze(
    request: Request,
    review_text: str = Form(...),
    db: Session = Depends(get_db)
):

    review_text = review_text.strip()

    if len(review_text) < 2 or len(review_text) > 5000:

        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={
                "result": None,
                "error": "리뷰는 2자 이상 5,000자 이하로 입력해 주세요."
            },
            status_code=400
        )

    service = ReviewService(db)

    result = service.analyze_review(review_text)

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "result": result
        }
    )


@router.get("/history", response_class=HTMLResponse)
def history(
    request: Request,
    db: Session = Depends(get_db)
):

    service = ReviewService(db)

    reviews = service.get_history()

    statistics = service.get_statistics()

    return templates.TemplateResponse(
        request=request,
        name="history.html",
        context={
            "reviews": reviews,
            "statistics": statistics
        }
    )