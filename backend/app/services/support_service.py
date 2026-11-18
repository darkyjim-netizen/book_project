"""공지사항, Q&A, FAQ 기능을 처리하는 서비스."""
import logging
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import BusinessError, NotFoundError
from app.models.enums import QnaStatus
from app.models.member import Member
from app.models.support import Faq, Notice, QnaAnswer, QnaQuestion
from app.schemas.support import (
    FaqCreateRequest,
    NoticeCreateRequest,
    NoticeUpdateRequest,
    QnaCreateRequest,
    QnaResponse,
)

logger = logging.getLogger(__name__)


class NoticeService:
    """공지사항 조회, 등록, 수정, 삭제를 담당한다."""

    def __init__(self, db: Session):
        # 서비스 메서드에서 사용할 DB 세션
        self.db = db

    def list_notices(
        self,
        page: int = 1,
        size: int = 10,
        category: Optional[str] = None,
        keyword: Optional[str] = None,
        include_unpublished: bool = False,
    ) -> Tuple[List[Notice], int]:
        """공지 목록을 조회한다. 상단 고정 공지가 먼저 나온다."""

        # 아래 조건들을 하나씩 추가해 최종 검색 조건을 만든다.
        conditions = []

        # 비공개 공지를 포함하지 않는 경우 게시 중인 공지만 조회한다.
        if not include_unpublished:
            conditions.append(Notice.is_published == True)  # noqa: E712

        # 카테고리가 전달되면 해당 카테고리의 공지만 조회한다.
        if category:
            conditions.append(Notice.category == category)

        # 검색어가 있으면 제목이나 내용에 해당 단어가 포함된 공지를 찾는다.
        if keyword:
            kw = f"%{keyword}%"
            conditions.append(
                or_(
                    Notice.title.ilike(kw),
                    Notice.content.ilike(kw),
                )
            )

        # 페이지에 상관없이 조건에 맞는 전체 공지 수를 계산한다.
        total = (
            self.db.scalar(
                select(func.count())
                .select_from(Notice)
                .where(*conditions)
            )
            or 0
        )

        # 고정 공지를 먼저, 그다음 최근 게시된 순서로 공지를 가져온다.
        rows = list(
            self.db.scalars(
                select(Notice)
                .where(*conditions)
                .order_by(
                    Notice.is_pinned.desc(),
                    Notice.published_at.desc(),
                )
                # 페이지 번호와 페이지 크기를 이용해 일부만 가져온다.
                .offset((page - 1) * size)
                .limit(size)
            ).unique()
        )

        return rows, total

    def get_notice(
        self,
        notice_id: int,
        increase_view: bool = True,
    ) -> Notice:
        """공지 하나를 조회하고, 설정에 따라 조회수를 올린다."""

        # 첨부 파일 정보도 함께 불러온다.
        notice = self.db.scalar(
            select(Notice)
            .options(selectinload(Notice.attachments))
            .where(Notice.notice_id == notice_id)
        )

        if notice is None:
            raise NotFoundError("공지사항을 찾을 수 없습니다.")

        # 상세 페이지 조회처럼 조회수를 올려야 하는 경우에만 증가시킨다.
        if increase_view:
            notice.view_count = (notice.view_count or 0) + 1
            self.db.commit()

        return notice

    def get_adjacent(self, notice_id: int) -> dict:
        """현재 공지의 이전글과 다음글 정보를 조회한다."""

        current = self.db.get(Notice, notice_id)
        if current is None:
            raise NotFoundError("공지사항을 찾을 수 없습니다.")

        # 현재 공지보다 먼저 게시된 공지 중 가장 최근 글을 찾는다.
        prev_item = self.db.scalar(
            select(Notice)
            .where(
                Notice.is_published == True,  # noqa: E712
                Notice.published_at < current.published_at,
            )
            .order_by(Notice.published_at.desc())
            .limit(1)
        )

        # 현재 공지보다 나중에 게시된 공지 중 가장 오래된 글을 찾는다.
        next_item = self.db.scalar(
            select(Notice)
            .where(
                Notice.is_published == True,  # noqa: E712
                Notice.published_at > current.published_at,
            )
            .order_by(Notice.published_at.asc())
            .limit(1)
        )

        # 이전글이나 다음글이 없으면 해당 값은 None으로 반환한다.
        return {
            "prev": (
                {
                    "notice_id": prev_item.notice_id,
                    "title": prev_item.title,
                }
                if prev_item
                else None
            ),
            "next": (
                {
                    "notice_id": next_item.notice_id,
                    "title": next_item.title,
                }
                if next_item
                else None
            ),
        }

    def create_notice(
        self,
        payload: NoticeCreateRequest,
        author_id: int,
    ) -> Notice:
        """새 공지사항을 등록한다."""

        # 요청 데이터를 공지사항 객체로 바꾸고 작성자 번호를 추가한다.
        notice = Notice(
            **payload.model_dump(),
            author_id=author_id,
        )
        self.db.add(notice)
        self.db.commit()
        self.db.refresh(notice)

        logger.info("공지 등록: notice_id=%s", notice.notice_id)
        return notice

    def update_notice(
        self,
        notice_id: int,
        payload: NoticeUpdateRequest,
    ) -> Notice:
        """공지사항에서 요청으로 전달된 항목만 수정한다."""

        notice = self.db.get(Notice, notice_id)
        if notice is None:
            raise NotFoundError("공지사항을 찾을 수 없습니다.")

        # exclude_unset=True는 요청에서 보내지 않은 필드를 제외한다.
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(notice, key, value)

        self.db.commit()
        self.db.refresh(notice)
        return notice

    def delete_notice(self, notice_id: int) -> None:
        """공지사항을 삭제한다."""

        notice = self.db.get(Notice, notice_id)
        if notice is None:
            raise NotFoundError("공지사항을 찾을 수 없습니다.")

        self.db.delete(notice)
        self.db.commit()


class QnaService:
    """Q&A 질문과 답변을 처리한다."""

    def __init__(self, db: Session):
        self.db = db

    def to_response(
        self,
        q: QnaQuestion,
        viewer: Optional[Member] = None,
    ) -> QnaResponse:
        """Q&A 질문을 응답 형식으로 바꾸며 비밀글 권한을 확인한다."""

        # 공개 질문은 누구나 볼 수 있다고 기본 설정한다.
        can_view = True

        if q.is_secret:
            # 비밀글은 질문 작성자 본인이나 관리자만 내용을 볼 수 있다.
            can_view = (
                viewer is not None
                and (
                    viewer.member_id == q.member_id
                    or viewer.is_admin
                )
            )

        # 작성자 이름을 응답에 표시하되, 이름을 별표로 가린다.
        name = q.member.name if q.member else "회원"
        masked = name[0] + "*" * max(len(name) - 1, 1)

        # 답변 응답 스키마를 이 함수에서만 사용하므로 필요한 시점에 가져온다.
        from app.schemas.support import QnaAnswerResponse

        return QnaResponse(
            question_id=q.question_id,
            category=q.category,
            # 볼 권한이 없으면 제목과 본문 대신 비밀글 안내를 보여준다.
            title=q.title if can_view else "비밀글입니다.",
            content=q.content if can_view else None,
            status=q.status.value,
            is_secret=q.is_secret,
            member_name=masked,
            book_id=q.book_id,
            book_title=None,
            view_count=q.view_count,
            # 질문을 볼 수 있는 사람에게만 답변 내용을 반환한다.
            answers=(
                [
                    QnaAnswerResponse.model_validate(answer)
                    for answer in q.answers
                ]
                if can_view
                else []
            ),
            created_at=q.created_at,
        )

    def list_questions(
        self,
        page: int = 1,
        size: int = 10,
        member: Optional[Member] = None,
        only_mine: bool = False,
        status: Optional[str] = None,
        category: Optional[str] = None,
        keyword: Optional[str] = None,
    ) -> Tuple[List[QnaQuestion], int]:
        """Q&A 질문 목록을 조건에 맞춰 조회한다."""

        conditions = []

        # only_mine=True이면 로그인한 회원 본인의 질문만 조회한다.
        if only_mine:
            if member is None:
                raise BusinessError(
                    "로그인이 필요합니다.",
                    status_code=401,
                )
            conditions.append(
                QnaQuestion.member_id == member.member_id
            )

        # 상태, 카테고리, 제목 검색어가 전달되면 조회 조건에 추가한다.
        if status:
            conditions.append(
                QnaQuestion.status == QnaStatus(status)
            )

        if category:
            conditions.append(QnaQuestion.category == category)

        if keyword:
            conditions.append(
                QnaQuestion.title.ilike(f"%{keyword}%")
            )

        # 검색 조건에 맞는 전체 질문 수를 계산한다.
        total = (
            self.db.scalar(
                select(func.count())
                .select_from(QnaQuestion)
                .where(*conditions)
            )
            or 0
        )

        # 질문의 답변과 작성자 정보도 함께 가져온다.
        rows = list(
            self.db.scalars(
                select(QnaQuestion)
                .options(
                    selectinload(QnaQuestion.answers),
                    selectinload(QnaQuestion.member),
                )
                .where(*conditions)
                .order_by(QnaQuestion.created_at.desc())
                .offset((page - 1) * size)
                .limit(size)
            ).unique()
        )

        return rows, total

    def get_question(
        self,
        question_id: int,
        increase_view: bool = True,
    ) -> QnaQuestion:
        """질문 하나와 답변·작성자 정보를 조회한다."""

        q = self.db.scalar(
            select(QnaQuestion)
            .options(
                selectinload(QnaQuestion.answers),
                selectinload(QnaQuestion.member),
            )
            .where(QnaQuestion.question_id == question_id)
        )

        if q is None:
            raise NotFoundError("문의를 찾을 수 없습니다.")

        # 조회수를 올리는 요청이면 조회수를 1 증가시킨다.
        if increase_view:
            q.view_count = (q.view_count or 0) + 1
            self.db.commit()

        return q

    def create_question(
        self,
        member: Member,
        payload: QnaCreateRequest,
    ) -> QnaQuestion:
        """로그인 회원의 Q&A 질문을 등록한다."""

        # 요청 데이터에 작성자 회원 번호를 넣어 질문 객체를 만든다.
        q = QnaQuestion(
            **payload.model_dump(),
            member_id=member.member_id,
        )
        self.db.add(q)
        self.db.commit()
        self.db.refresh(q)

        logger.info(
            "Q&A 등록: question_id=%s member_id=%s",
            q.question_id,
            member.member_id,
        )
        return q

    def delete_question(
        self,
        question_id: int,
        member: Member,
    ) -> None:
        """질문 작성자 본인이나 관리자가 질문을 삭제한다."""

        q = self.db.get(QnaQuestion, question_id)
        if q is None:
            raise NotFoundError("문의를 찾을 수 없습니다.")

        # 본인 질문이 아니고 관리자도 아니면 삭제를 허용하지 않는다.
        if q.member_id != member.member_id and not member.is_admin:
            raise BusinessError(
                "본인의 문의만 삭제할 수 있습니다.",
                status_code=403,
            )

        self.db.delete(q)
        self.db.commit()

    def answer(
        self,
        question_id: int,
        admin: Member,
        content: str,
    ) -> QnaAnswer:
        """관리자가 질문에 답변을 등록한다."""

        q = self.db.get(QnaQuestion, question_id)
        if q is None:
            raise NotFoundError("문의를 찾을 수 없습니다.")

        # 답변 내용과 답변을 작성한 관리자 번호를 저장한다.
        answer = QnaAnswer(
            question_id=question_id,
            admin_id=admin.member_id,
            content=content,
        )
        self.db.add(answer)

        # 답변이 등록되었으므로 질문 상태를 답변 완료로 바꾼다.
        q.status = QnaStatus.ANSWERED

        self.db.commit()
        self.db.refresh(answer)

        logger.info("Q&A 답변 등록: question_id=%s", question_id)
        return answer

    def update_answer(
        self,
        answer_id: int,
        content: str,
    ) -> QnaAnswer:
        """기존 답변의 내용을 수정한다."""

        answer = self.db.get(QnaAnswer, answer_id)
        if answer is None:
            raise NotFoundError("답변을 찾을 수 없습니다.")

        answer.content = content
        answer.updated_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(answer)
        return answer

    def close_question(self, question_id: int) -> QnaQuestion:
        """질문을 종료 상태로 바꾼다."""

        q = self.db.get(QnaQuestion, question_id)
        if q is None:
            raise NotFoundError("문의를 찾을 수 없습니다.")

        q.status = QnaStatus.CLOSED

        self.db.commit()
        self.db.refresh(q)
        return q

    def waiting_count(self) -> int:
        """답변을 기다리는 질문의 수를 반환한다."""

        return (
            self.db.scalar(
                select(func.count())
                .select_from(QnaQuestion)
                .where(QnaQuestion.status == QnaStatus.WAITING)
            )
            or 0
        )


class FaqService:
    """FAQ 조회, 등록, 삭제를 처리한다."""

    def __init__(self, db: Session):
        self.db = db

    def list_faqs(
        self,
        category: Optional[str] = None,
    ) -> List[Faq]:
        """사용 중인 FAQ를 조회하고, 필요하면 카테고리로 필터링한다."""

        # 비활성 FAQ는 기본 조회 결과에서 제외한다.
        conditions = [Faq.is_active == True]  # noqa: E712

        if category:
            conditions.append(Faq.category == category)

        # 카테고리와 정렬 순서에 따라 FAQ를 가져온다.
        return list(
            self.db.scalars(
                select(Faq)
                .where(*conditions)
                .order_by(Faq.category, Faq.sort_order)
            ).unique()
        )

    def categories(self) -> List[str]:
        """사용 중인 FAQ의 카테고리 목록을 중복 없이 반환한다."""

        rows = self.db.execute(
            select(Faq.category)
            .where(Faq.is_active == True)  # noqa: E712
            .group_by(Faq.category)
        ).all()

        return [row[0] for row in rows]

    def create_faq(self, payload: FaqCreateRequest) -> Faq:
        """새 FAQ를 등록한다."""

        faq = Faq(**payload.model_dump())
        self.db.add(faq)
        self.db.commit()
        self.db.refresh(faq)
        return faq

    def delete_faq(self, faq_id: int) -> None:
        """FAQ를 삭제한다."""

        faq = self.db.get(Faq, faq_id)
        if faq is None:
            raise NotFoundError("FAQ를 찾을 수 없습니다.")

        self.db.delete(faq)
        self.db.commit()