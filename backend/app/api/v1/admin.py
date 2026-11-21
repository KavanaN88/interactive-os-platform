"""Administrator API. The router-level dependency makes EVERY route here require an administrator (401 if not signed in,
403 for students); handlers also receive the acting admin so each change is written to the audit log."""
from fastapi import APIRouter, Depends, Request

from app.api.v1.common import api_errors
from app.api.v1.deps import client_ip, require_admin
from app.auth import admin as ops
from app.schemas.auth import PasswordReset, QuestionIn, TopicIn, UserPatch, Visibility

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/stats")
def stats():
    return ops.stats()


@router.get("/performance")
def performance():
    return ops.performance()


@router.get("/audit")
def audit(limit: int = 100, action: str | None = None):
    with api_errors():
        return ops.audit_list(limit, action)


@router.get("/users")
def users(search: str | None = None, role: str | None = None, active: bool | None = None, limit: int = 25, offset: int = 0):
    with api_errors():
        return ops.list_users(search, role, active, limit, offset)


@router.patch("/users/{user_id}")
def patch_user(user_id: str, req: UserPatch, request: Request, admin: dict = Depends(require_admin)):
    with api_errors():
        return ops.update_user(admin, user_id, req.is_active, req.role, ip=client_ip(request))


@router.post("/users/{user_id}/reset-password")
def reset_password(user_id: str, req: PasswordReset, request: Request, admin: dict = Depends(require_admin)):
    with api_errors():
        ops.reset_password(admin, user_id, req.new_password, ip=client_ip(request))
    return {"ok": True}


@router.delete("/users/{user_id}")
def delete_user(user_id: str, request: Request, admin: dict = Depends(require_admin)):
    with api_errors():
        ops.delete_user(admin, user_id, ip=client_ip(request))
    return {"ok": True}


@router.get("/topics")
def topics():
    return ops.list_topics()


@router.get("/topics/{topic_id}")
def topic(topic_id: str):
    with api_errors():
        return ops.get_topic_admin(topic_id)


@router.post("/topics", status_code=201)
def create_topic(req: TopicIn, request: Request, admin: dict = Depends(require_admin)):
    with api_errors():
        return ops.create_topic(admin, req.model_dump(), ip=client_ip(request))


@router.put("/topics/{topic_id}")
def update_topic(topic_id: str, req: TopicIn, request: Request, admin: dict = Depends(require_admin)):
    with api_errors():
        return ops.update_topic(admin, topic_id, req.model_dump(), ip=client_ip(request))


@router.delete("/topics/{topic_id}")
def delete_topic(topic_id: str, request: Request, admin: dict = Depends(require_admin)):
    with api_errors():
        ops.delete_topic(admin, topic_id, ip=client_ip(request))
    return {"ok": True}


@router.post("/topics/{topic_id}/visibility")
def topic_visibility(topic_id: str, req: Visibility, request: Request, admin: dict = Depends(require_admin)):
    with api_errors():
        ops.set_topic_published(admin, topic_id, req.published, ip=client_ip(request))
    return {"ok": True}


@router.get("/questions")
def questions():
    return ops.list_questions()


@router.post("/questions", status_code=201)
def create_question(req: QuestionIn, request: Request, admin: dict = Depends(require_admin)):
    with api_errors():
        return ops.create_question(admin, req.model_dump(), ip=client_ip(request))


@router.put("/questions/{question_id}")
def update_question(question_id: str, req: QuestionIn, request: Request, admin: dict = Depends(require_admin)):
    with api_errors():
        return ops.update_question(admin, question_id, req.model_dump(), ip=client_ip(request))


@router.delete("/questions/{question_id}")
def delete_question(question_id: str, request: Request, admin: dict = Depends(require_admin)):
    with api_errors():
        ops.delete_question(admin, question_id, ip=client_ip(request))
    return {"ok": True}


@router.post("/questions/{question_id}/visibility")
def question_visibility(question_id: str, req: Visibility, request: Request, admin: dict = Depends(require_admin)):
    with api_errors():
        ops.set_question_published(admin, question_id, req.published, ip=client_ip(request))
    return {"ok": True}
