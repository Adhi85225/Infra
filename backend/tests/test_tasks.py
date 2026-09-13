"""Task Updates: listing, filtering, creation, editing and authorization.

The authorization rules under test:

* **Task Updates page** (no ``service`` filter) -- every task is visible to
  every caller who can view the module.
* **Service pages** (``service`` supplied) -- a task administrator sees all
  users and may filter by one; everybody else is pinned to their own rows.
* **Editing** -- administrators edit anything, everyone else only their own.

A task administrator is a caller holding MANAGE on ACCESS_MANAGEMENT, which the
seeded ADMIN role has and the USER and GUEST roles do not.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from tests.conftest import (
    ADMIN_PASSWORD,
    GUEST_PASSWORD,
    USER_PASSWORD,
    auth_headers,
)

TODAY = date.today()
YESTERDAY = TODAY - timedelta(days=1)
LAST_WEEK = TODAY - timedelta(days=7)


async def _headers(client, user, password):
    return await auth_headers(client, user.email, password)


async def _create(client, headers, **overrides):
    """POST a task, defaulting every required field."""
    payload = {
        "task_date": str(TODAY),
        "description": "Investigated an alert",
        "service": "DAS",
        "status": "Created",
    }
    payload.update(overrides)
    response = await client.post("/api/v1/tasks", json=payload, headers=headers)
    return response


# ---------------------------------------------------------------------------
# Dropdown options (D1 / D2)
# ---------------------------------------------------------------------------


async def test_options_expose_the_exact_dropdown_values(client, normal_user):
    headers = await _headers(client, normal_user, USER_PASSWORD)
    response = await client.get("/api/v1/tasks/options", headers=headers)

    assert response.status_code == 200
    body = response.json()
    # Spelling is part of the contract: these strings are stored, filtered and
    # displayed unchanged.
    assert body["services"] == ["Access Management", "DAS", "ILO", "Zabbix", "Nexus", "Servers"]
    assert body["statuses"] == ["Created", "Inprogress", "Onhold", "Completed", "Triage"]


# ---------------------------------------------------------------------------
# Creation
# ---------------------------------------------------------------------------


async def test_user_can_add_a_task(client, normal_user):
    headers = await _headers(client, normal_user, USER_PASSWORD)
    response = await _create(
        client,
        headers,
        reference_number="INC-1024",
        site_name="Chennai DC",
        remarks="Waiting on vendor",
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["reference_number"] == "INC-1024"
    assert body["site_name"] == "Chennai DC"
    assert body["service"] == "DAS"
    assert body["status"] == "Created"
    # The task belongs to its author, and the author may edit it.
    assert body["user_id"] == str(normal_user.id)
    assert body["user_name"] == normal_user.full_name
    assert body["can_edit"] is True


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("description", ""),
        ("description", "   "),
        ("service", "Storage"),
        ("status", "In Progress"),
        ("task_date", "not-a-date"),
    ],
)
async def test_invalid_fields_are_rejected(client, normal_user, field, value):
    headers = await _headers(client, normal_user, USER_PASSWORD)
    response = await _create(client, headers, **{field: value})
    assert response.status_code == 422, response.text


async def test_missing_required_fields_are_rejected(client, normal_user):
    headers = await _headers(client, normal_user, USER_PASSWORD)
    response = await client.post(
        "/api/v1/tasks", json={"description": "no date or service"}, headers=headers
    )
    assert response.status_code == 422


async def test_blank_optional_fields_are_stored_as_null(client, normal_user):
    headers = await _headers(client, normal_user, USER_PASSWORD)
    response = await _create(client, headers, reference_number="   ", site_name="", remarks="")

    assert response.status_code == 201
    body = response.json()
    assert body["reference_number"] is None
    assert body["site_name"] is None
    assert body["remarks"] is None


async def test_view_only_caller_cannot_add_a_task(client, guest):
    # GUEST holds READ_ONLY on TASK_UPDATES, which permits VIEW and nothing else.
    headers = await _headers(client, guest, GUEST_PASSWORD)
    response = await _create(client, headers)
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Task Updates page: every task is visible to everyone
# ---------------------------------------------------------------------------


async def test_task_updates_page_shows_every_users_tasks(client, admin, normal_user):
    admin_headers = await _headers(client, admin, ADMIN_PASSWORD)
    user_headers = await _headers(client, normal_user, USER_PASSWORD)

    assert (await _create(client, admin_headers, description="Admin task")).status_code == 201
    assert (await _create(client, user_headers, description="User task")).status_code == 201

    # The normal user sees the administrator's task too: the global page is not
    # scoped by owner.
    response = await client.get("/api/v1/tasks", headers=user_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert {item["description"] for item in body["items"]} == {"Admin task", "User task"}


async def test_task_updates_page_marks_only_own_rows_editable(client, admin, normal_user):
    admin_headers = await _headers(client, admin, ADMIN_PASSWORD)
    user_headers = await _headers(client, normal_user, USER_PASSWORD)

    await _create(client, admin_headers, description="Admin task")
    await _create(client, user_headers, description="User task")

    body = (await client.get("/api/v1/tasks", headers=user_headers)).json()
    editable = {item["description"]: item["can_edit"] for item in body["items"]}
    assert editable == {"Admin task": False, "User task": True}


# ---------------------------------------------------------------------------
# Service pages
# ---------------------------------------------------------------------------


async def test_service_page_returns_only_that_service(client, admin):
    headers = await _headers(client, admin, ADMIN_PASSWORD)
    await _create(client, headers, service="DAS", description="das work")
    await _create(client, headers, service="Nexus", description="nexus work")

    body = (await client.get("/api/v1/tasks?service=DAS", headers=headers)).json()
    assert body["total"] == 1
    assert body["items"][0]["description"] == "das work"


async def test_service_page_scopes_a_normal_user_to_their_own_tasks(client, admin, normal_user):
    admin_headers = await _headers(client, admin, ADMIN_PASSWORD)
    user_headers = await _headers(client, normal_user, USER_PASSWORD)

    await _create(client, admin_headers, service="DAS", description="admin das")
    await _create(client, user_headers, service="DAS", description="user das")

    body = (await client.get("/api/v1/tasks?service=DAS", headers=user_headers)).json()
    assert body["total"] == 1
    assert body["items"][0]["description"] == "user das"


async def test_service_page_shows_an_admin_every_users_tasks(client, admin, normal_user):
    admin_headers = await _headers(client, admin, ADMIN_PASSWORD)
    user_headers = await _headers(client, normal_user, USER_PASSWORD)

    await _create(client, admin_headers, service="DAS", description="admin das")
    await _create(client, user_headers, service="DAS", description="user das")

    body = (await client.get("/api/v1/tasks?service=DAS", headers=admin_headers)).json()
    assert body["total"] == 2


async def test_admin_can_filter_a_service_page_by_user(client, admin, normal_user):
    admin_headers = await _headers(client, admin, ADMIN_PASSWORD)
    user_headers = await _headers(client, normal_user, USER_PASSWORD)

    await _create(client, admin_headers, service="DAS", description="admin das")
    await _create(client, user_headers, service="DAS", description="user das")

    body = (
        await client.get(
            f"/api/v1/tasks?service=DAS&user_id={normal_user.id}", headers=admin_headers
        )
    ).json()
    assert body["total"] == 1
    assert body["items"][0]["description"] == "user das"


async def test_normal_user_cannot_widen_a_service_page_with_user_id(client, admin, normal_user):
    """The user filter is administrative; asking for someone else is ignored."""
    admin_headers = await _headers(client, admin, ADMIN_PASSWORD)
    user_headers = await _headers(client, normal_user, USER_PASSWORD)

    await _create(client, admin_headers, service="DAS", description="admin das")
    await _create(client, user_headers, service="DAS", description="user das")

    body = (
        await client.get(f"/api/v1/tasks?service=DAS&user_id={admin.id}", headers=user_headers)
    ).json()
    # Pinned to their own rows regardless of the requested filter.
    assert body["total"] == 1
    assert body["items"][0]["description"] == "user das"


# ---------------------------------------------------------------------------
# Filtering, search and sorting
# ---------------------------------------------------------------------------


async def test_date_filters(client, normal_user):
    headers = await _headers(client, normal_user, USER_PASSWORD)
    await _create(client, headers, task_date=str(TODAY), description="today task")
    await _create(client, headers, task_date=str(YESTERDAY), description="yesterday task")
    await _create(client, headers, task_date=str(LAST_WEEK), description="old task")

    today = (
        await client.get(f"/api/v1/tasks?date_from={TODAY}&date_to={TODAY}", headers=headers)
    ).json()
    assert [item["description"] for item in today["items"]] == ["today task"]

    yesterday = (
        await client.get(
            f"/api/v1/tasks?date_from={YESTERDAY}&date_to={YESTERDAY}", headers=headers
        )
    ).json()
    assert [item["description"] for item in yesterday["items"]] == ["yesterday task"]

    # Custom date: an arbitrary single day.
    custom = (
        await client.get(
            f"/api/v1/tasks?date_from={LAST_WEEK}&date_to={LAST_WEEK}", headers=headers
        )
    ).json()
    assert [item["description"] for item in custom["items"]] == ["old task"]


@pytest.mark.parametrize(
    ("term", "expected"),
    [
        ("INC-1024", "reference hit"),
        ("chennai", "site hit"),
        ("replaced a disk", "replaced a disk"),
        ("vendor", "remarks hit"),
        ("Onhold", "status hit"),
    ],
)
async def test_search_covers_the_textual_columns(client, normal_user, term, expected):
    headers = await _headers(client, normal_user, USER_PASSWORD)
    await _create(client, headers, description="reference hit", reference_number="INC-1024")
    await _create(client, headers, description="site hit", site_name="Chennai DC")
    await _create(client, headers, description="replaced a disk")
    await _create(client, headers, description="remarks hit", remarks="Waiting on vendor")
    await _create(client, headers, description="status hit", status="Onhold")

    body = (await client.get(f"/api/v1/tasks?search={term}", headers=headers)).json()
    assert expected in [item["description"] for item in body["items"]]


async def test_search_matches_the_owning_user(client, admin, normal_user):
    admin_headers = await _headers(client, admin, ADMIN_PASSWORD)
    user_headers = await _headers(client, normal_user, USER_PASSWORD)
    await _create(client, admin_headers, description="admin task")
    await _create(client, user_headers, description="user task")

    body = (await client.get("/api/v1/tasks?search=Normal", headers=user_headers)).json()
    assert [item["description"] for item in body["items"]] == ["user task"]


async def test_default_sort_is_newest_first(client, normal_user):
    headers = await _headers(client, normal_user, USER_PASSWORD)
    await _create(client, headers, task_date=str(LAST_WEEK), description="old")
    await _create(client, headers, task_date=str(TODAY), description="new")
    await _create(client, headers, task_date=str(YESTERDAY), description="middle")

    body = (await client.get("/api/v1/tasks", headers=headers)).json()
    assert [item["description"] for item in body["items"]] == ["new", "middle", "old"]


#: Two rows whose every sortable column differs, with "first" ordering before
#: "second" in all of them. One pair therefore exercises every column.
_SORT_FIRST = {
    "task_date": str(YESTERDAY),
    "reference_number": "AAA-1",
    "site_name": "Alpha Site",
    "description": "aaa first",
    "status": "Created",
    "remarks": "aaa remark",
    "service": "DAS",
}
_SORT_SECOND = {
    "task_date": str(TODAY),
    "reference_number": "BBB-2",
    "site_name": "Beta Site",
    "description": "bbb second",
    "status": "Triage",
    "remarks": "bbb remark",
    "service": "Nexus",
}


@pytest.mark.parametrize("column", sorted(_SORT_FIRST))
async def test_every_column_is_sortable_in_both_directions(client, normal_user, column):
    headers = await _headers(client, normal_user, USER_PASSWORD)
    await _create(client, headers, **_SORT_FIRST)
    await _create(client, headers, **_SORT_SECOND)

    ascending = (
        await client.get(f"/api/v1/tasks?sort_by={column}&direction=asc", headers=headers)
    ).json()
    descending = (
        await client.get(f"/api/v1/tasks?sort_by={column}&direction=desc", headers=headers)
    ).json()

    assert ascending["total"] == descending["total"] == 2
    assert [item["description"] for item in ascending["items"]] == [
        "aaa first",
        "bbb second",
    ]
    assert [item["description"] for item in descending["items"]] == [
        "bbb second",
        "aaa first",
    ]


async def test_ties_keep_a_stable_order_across_pages(client, normal_user):
    """Equal sort values must not reshuffle between requests.

    Every row here shares a task_date, so only the tiebreaker distinguishes
    them. It is deliberately constant rather than flipping with `direction`,
    which is what makes paging through ties safe.
    """
    headers = await _headers(client, normal_user, USER_PASSWORD)
    for index in range(6):
        await _create(client, headers, task_date=str(TODAY), description=f"tied {index}")

    first = await client.get("/api/v1/tasks?limit=3&offset=0", headers=headers)
    second = await client.get("/api/v1/tasks?limit=3&offset=3", headers=headers)
    again = await client.get("/api/v1/tasks?limit=3&offset=0", headers=headers)

    page_one = [item["id"] for item in first.json()["items"]]
    page_two = [item["id"] for item in second.json()["items"]]

    assert page_one == [item["id"] for item in again.json()["items"]]
    # No row appears on both pages, and none is skipped.
    assert set(page_one).isdisjoint(page_two)
    assert len(set(page_one) | set(page_two)) == 6


async def test_sorting_by_user_orders_by_name(client, admin, normal_user):
    admin_headers = await _headers(client, admin, ADMIN_PASSWORD)
    user_headers = await _headers(client, normal_user, USER_PASSWORD)
    await _create(client, user_headers, description="by normal")
    await _create(client, admin_headers, description="by admin")

    body = (
        await client.get("/api/v1/tasks?sort_by=user&direction=asc", headers=user_headers)
    ).json()
    # "Admin User" sorts before "Normal User".
    assert [item["description"] for item in body["items"]] == ["by admin", "by normal"]


async def test_sorting_combines_with_search_and_filters(client, normal_user):
    headers = await _headers(client, normal_user, USER_PASSWORD)
    await _create(client, headers, service="DAS", description="disk one", site_name="Beta")
    await _create(client, headers, service="DAS", description="disk two", site_name="Alpha")
    await _create(client, headers, service="Nexus", description="disk three", site_name="Gamma")

    body = (
        await client.get(
            f"/api/v1/tasks?service=DAS&search=disk&sort_by=site_name&direction=asc"
            f"&date_from={TODAY}&date_to={TODAY}",
            headers=headers,
        )
    ).json()
    assert [item["description"] for item in body["items"]] == ["disk two", "disk one"]


async def test_unknown_sort_column_is_rejected(client, normal_user):
    headers = await _headers(client, normal_user, USER_PASSWORD)
    response = await client.get("/api/v1/tasks?sort_by=password_hash", headers=headers)
    assert response.status_code == 422


async def test_pagination_reports_the_unpaginated_total(client, normal_user):
    headers = await _headers(client, normal_user, USER_PASSWORD)
    for index in range(5):
        await _create(client, headers, description=f"task {index}")

    body = (await client.get("/api/v1/tasks?limit=2&offset=0", headers=headers)).json()
    assert body["total"] == 5
    assert len(body["items"]) == 2


# ---------------------------------------------------------------------------
# Editing
# ---------------------------------------------------------------------------


async def test_owner_can_edit_their_task(client, normal_user):
    headers = await _headers(client, normal_user, USER_PASSWORD)
    task_id = (await _create(client, headers)).json()["id"]

    response = await client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"status": "Completed", "remarks": "Closed off"},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "Completed"
    assert body["remarks"] == "Closed off"
    # Untouched fields survive a partial update.
    assert body["description"] == "Investigated an alert"


async def test_single_task_can_be_fetched_for_editing(client, normal_user):
    headers = await _headers(client, normal_user, USER_PASSWORD)
    created = (await _create(client, headers, reference_number="INC-77")).json()

    response = await client.get(f"/api/v1/tasks/{created['id']}", headers=headers)
    assert response.status_code == 200
    assert response.json()["reference_number"] == "INC-77"


async def test_normal_user_cannot_edit_another_users_task(client, admin, normal_user):
    admin_headers = await _headers(client, admin, ADMIN_PASSWORD)
    user_headers = await _headers(client, normal_user, USER_PASSWORD)
    task_id = (await _create(client, admin_headers)).json()["id"]

    # Hiding the edit icon is not the boundary -- the API refuses outright.
    response = await client.patch(
        f"/api/v1/tasks/{task_id}", json={"status": "Completed"}, headers=user_headers
    )
    assert response.status_code == 403


async def test_admin_can_edit_another_users_task(client, admin, normal_user):
    admin_headers = await _headers(client, admin, ADMIN_PASSWORD)
    user_headers = await _headers(client, normal_user, USER_PASSWORD)
    task_id = (await _create(client, user_headers)).json()["id"]

    response = await client.patch(
        f"/api/v1/tasks/{task_id}", json={"status": "Triage"}, headers=admin_headers
    )
    assert response.status_code == 200
    assert response.json()["status"] == "Triage"


async def test_view_only_caller_cannot_edit(client, admin, guest):
    admin_headers = await _headers(client, admin, ADMIN_PASSWORD)
    guest_headers = await _headers(client, guest, GUEST_PASSWORD)
    task_id = (await _create(client, admin_headers)).json()["id"]

    response = await client.patch(
        f"/api/v1/tasks/{task_id}", json={"status": "Completed"}, headers=guest_headers
    )
    assert response.status_code == 403


async def test_editing_an_unknown_task_is_not_found(client, normal_user):
    headers = await _headers(client, normal_user, USER_PASSWORD)
    response = await client.patch(
        "/api/v1/tasks/00000000-0000-0000-0000-000000000000",
        json={"status": "Completed"},
        headers=headers,
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Security: ownership cannot be forged
# ---------------------------------------------------------------------------


async def test_normal_user_cannot_file_a_task_against_someone_else(client, admin, normal_user):
    user_headers = await _headers(client, normal_user, USER_PASSWORD)
    response = await _create(client, user_headers, user_id=str(admin.id))

    assert response.status_code == 201
    # The requested owner is ignored, not honoured.
    assert response.json()["user_id"] == str(normal_user.id)


async def test_normal_user_cannot_reassign_their_task(client, admin, normal_user):
    user_headers = await _headers(client, normal_user, USER_PASSWORD)
    task_id = (await _create(client, user_headers)).json()["id"]

    response = await client.patch(
        f"/api/v1/tasks/{task_id}", json={"user_id": str(admin.id)}, headers=user_headers
    )
    assert response.status_code == 200
    assert response.json()["user_id"] == str(normal_user.id)


async def test_admin_can_file_a_task_for_another_user(client, admin, normal_user):
    admin_headers = await _headers(client, admin, ADMIN_PASSWORD)
    response = await _create(client, admin_headers, user_id=str(normal_user.id))

    assert response.status_code == 201
    assert response.json()["user_id"] == str(normal_user.id)
    assert response.json()["user_name"] == normal_user.full_name


async def test_anonymous_callers_are_rejected(client):
    assert (await client.get("/api/v1/tasks")).status_code == 401
    assert (await client.post("/api/v1/tasks", json={})).status_code == 401
