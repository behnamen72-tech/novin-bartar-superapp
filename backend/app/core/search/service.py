from uuid import UUID

from sqlalchemy.orm import Session

from app.core.documents.service import list_documents
from app.core.organization.service import search_organizations_for_user
from app.core.people.service import search_people_for_user
from app.core.search.schemas import SearchEntityType, SearchResponse, SearchResultItem
from app.modules.customers.service import search_customers_for_user
from app.modules.suppliers.service import search_suppliers_for_user

DEFAULT_TYPES: tuple[SearchEntityType, ...] = (
    SearchEntityType.ORGANIZATION,
    SearchEntityType.PERSON,
    SearchEntityType.DOCUMENT,
    SearchEntityType.CUSTOMER,
    SearchEntityType.SUPPLIER,
)


def search_core(
    session: Session,
    *,
    user_id: UUID,
    query: str,
    entity_types: tuple[SearchEntityType, ...] = DEFAULT_TYPES,
    limit_per_type: int = 8,
) -> SearchResponse:
    """Permission-aware federated search over Core domains.

    Search never introduces a new authorization boundary. Each provider performs
    its canonical domain read checks before rows are returned. This keeps Search
    extensible while preventing it from becoming a side channel around B3/B5 ACLs.
    """
    normalized = " ".join(query.strip().split())
    results: list[SearchResultItem] = []
    counts: dict[str, int] = {}

    if SearchEntityType.ORGANIZATION in entity_types:
        organizations = search_organizations_for_user(
            session,
            user_id=user_id,
            query=normalized,
            limit=limit_per_type,
        )
        counts[SearchEntityType.ORGANIZATION.value] = len(organizations)
        results.extend(
            SearchResultItem(
                entity_type=SearchEntityType.ORGANIZATION,
                id=item.id,
                title=item.name,
                subtitle=f"{item.organization_type.value} · {item.code}",
                organization_id=item.id,
                organization_name=item.name,
                action_path="/?view=organizations",
            )
            for item in organizations
        )

    if SearchEntityType.PERSON in entity_types:
        people = search_people_for_user(
            session,
            user_id=user_id,
            query=normalized,
            limit=limit_per_type,
        )
        counts[SearchEntityType.PERSON.value] = len(people)
        for person in people:
            first_relationship = person.relationships[0] if person.relationships else None
            contact = person.email or person.phone
            relationship_label = (
                f"{first_relationship.organization_name} · {first_relationship.relationship_code}"
                if first_relationship is not None
                else None
            )
            subtitle = " · ".join(value for value in (relationship_label, contact) if value) or None
            results.append(
                SearchResultItem(
                    entity_type=SearchEntityType.PERSON,
                    id=person.id,
                    title=f"{person.first_name} {person.last_name}".strip(),
                    subtitle=subtitle,
                    organization_id=(
                        first_relationship.organization_id
                        if first_relationship is not None
                        else None
                    ),
                    organization_name=(
                        first_relationship.organization_name
                        if first_relationship is not None
                        else None
                    ),
                    action_path="/?view=people",
                )
            )

    if SearchEntityType.DOCUMENT in entity_types:
        documents = list_documents(
            session,
            user_id=user_id,
            search=normalized,
            limit=limit_per_type,
            offset=0,
        )
        counts[SearchEntityType.DOCUMENT.value] = len(documents)
        results.extend(
            SearchResultItem(
                entity_type=SearchEntityType.DOCUMENT,
                id=document.id,
                title=document.title,
                subtitle=(
                    f"{document.document_type} · "
                    f"{getattr(document.status, 'value', document.status)}"
                ),
                organization_id=document.organization_id,
                action_path="/?view=documents",
            )
            for document in documents
        )

    if SearchEntityType.CUSTOMER in entity_types:
        customers = search_customers_for_user(
            session,
            user_id=user_id,
            query=normalized,
            limit=limit_per_type,
        )
        counts[SearchEntityType.CUSTOMER.value] = len(customers)
        results.extend(
            SearchResultItem(
                entity_type=SearchEntityType.CUSTOMER,
                id=item.id,
                title=item.display_label,
                subtitle=f"{item.customer_type.value} · {item.commercial_status.value}",
                organization_id=item.organization_id,
                organization_name=item.organization.name if item.organization is not None else None,
                action_path="/?view=customers",
            )
            for item in customers
        )

    if SearchEntityType.SUPPLIER in entity_types:
        suppliers = search_suppliers_for_user(
            session,
            user_id=user_id,
            query=normalized,
            limit=limit_per_type,
        )
        counts[SearchEntityType.SUPPLIER.value] = len(suppliers)
        results.extend(
            SearchResultItem(
                entity_type=SearchEntityType.SUPPLIER,
                id=item.id,
                title=item.display_name,
                subtitle=f"{item.supplier_kind.value} · {item.commercial_status.value}",
                organization_id=item.organization_id,
                organization_name=item.organization.name if item.organization is not None else None,
                action_path="/?view=suppliers",
            )
            for item in suppliers
        )

    # Stable type-grouped ordering is intentional. Providers already rank their
    # own results; grouping makes the UI predictable and avoids cross-domain
    # relevance scores that would be misleading at this stage.
    return SearchResponse(query=normalized, results=results, counts=counts)
