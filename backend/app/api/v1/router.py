from fastapi import APIRouter

from app.api.v1.routes.access import router as access_router
from app.api.v1.routes.audit import router as audit_router
from app.api.v1.routes.auth import router as auth_router
from app.api.v1.routes.customers import router as customers_router
from app.api.v1.routes.document_categories import router as document_categories_router
from app.api.v1.routes.document_retention import router as document_retention_router
from app.api.v1.routes.documents import router as documents_router
from app.api.v1.routes.health import router as health_router
from app.api.v1.routes.hr import router as hr_router
from app.api.v1.routes.notifications import router as notifications_router
from app.api.v1.routes.organizations import router as organizations_router
from app.api.v1.routes.people import router as people_router
from app.api.v1.routes.search import router as search_router
from app.api.v1.routes.suppliers import router as suppliers_router
from app.api.v1.routes.users import router as users_router
from app.api.v1.routes.workflow import router as workflow_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(customers_router)
api_router.include_router(suppliers_router)
api_router.include_router(audit_router)
api_router.include_router(notifications_router)
api_router.include_router(search_router)
api_router.include_router(documents_router)
api_router.include_router(document_categories_router)
api_router.include_router(document_retention_router)
api_router.include_router(access_router)
api_router.include_router(organizations_router)
api_router.include_router(people_router)
api_router.include_router(users_router)
api_router.include_router(workflow_router)
api_router.include_router(hr_router)
