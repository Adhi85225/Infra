"""Dashboard analytics: aggregation, filters and the service -> module mapping.

The dashboard is a *global* overview like the Task Updates page -- every caller
sees figures spanning every user -- with one exception: only a task
administrator may narrow to a single user.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.models.enums import TaskService, TaskStatus
from app.modules.registry import MODULE_DEFINITIONS
from tests.conftest import ADMIN_PASSWORD, GUEST_PASSWORD, USER_PASSWORD, auth_headers

TODAY = date.today()
YESTERDAY = TODAY - timedelta(days=1)


async def _headers(client, user, password):
    return await auth_headers(client, user.email, password)


async def _create(client, headers, **overrides):
    payload = {
        "task_date": str(TODAY),
        "description": "A task",
        "service": "DAS",
        "status": "Created",
    }
    payload.update(overrides)
    response = await client.post("/api/v1/tasks", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


async def _analytics(client, headers, query: str = ""):
    response = await client.get(f"/api/v1/tasks/analytics{query}", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


# ---------------------------------------------------------------------------
# Services map onto the modules that already exist
# ---------------------------------------------------------------------------


def test_every_service_maps_to_a_real_module():
    """Task Updates attaches to existing pages; it does not invent its own."""
    keys = {module.key for module in MODULE_DEFINITIONS}
    for service in TaskService:
        assert service.module_key in keys, f"{service.value} points at a module that does not exist"


@pytest.mark.parametrize(
    ("service", "module_key"),
    [
        (TaskService.ACCESS_MANAGEMENT, "ACCESS_MANAGEMENT"),
        (TaskService.DAS, "DAS_ONBOARDING"),
        (TaskService.ILO, "ILO_INVENTORY"),
        (TaskService.ZABBIX, "ZABBIX"),
        (TaskService.NEXUS, "NEXUS"),
        (TaskService.SERVERS, "SERVERS"),
    ],
)
def test_service_module_mapping(service, module_key):
    assert service.module_key == module_key
    assert TaskService.for_module(module_key) is service


def test_no_module_route_is_nested_under_task_updates():
    """The services keep their own top-level routes, not sub-pages of this one."""
    for module in MODULE_DEFINITIONS:
        if module.key == "TASK_UPDATES":
            continue
        assert not module.route.startswith("/task-updates")


async def test_options_publish_the_service_module_mapping(client, normal_user):
    headers = await _headers(client, normal_user, USER_PASSWORD)
    body = (await client.get("/api/v1/tasks/options", headers=headers)).json()
    assert body["service_modules"]["DAS"] == "DAS_ONBOARDING"
    assert body["service_modules"]["Access Management"] == "ACCESS_MANAGEMENT"
    assert set(body["service_modules"]) == set(body["services"])


# ---------------------------------------------------------------------------
# Counts
# ---------------------------------------------------------------------------


async def test_summary_counts_come_from_the_database(client, normal_user):
    headers = await _headers(client, normal_user, USER_PASSWORD)
    await _create(client, headers, status="Created")
    await _create(client, headers, status="Inprogress")
    await _create(client, headers, status="Inprogress")
    await _create(client, headers, status="Completed")

    body = await _analytics(client, headers)
    counts = {row["status"]: row["count"] for row in body["by_status"]}

    assert body["total"] == 4
    assert counts["Created"] == 1
    assert counts["Inprogress"] == 2
    assert counts["Completed"] == 1


async def test_every_status_and_service_is_reported_including_zeroes(client, normal_user):
    """A KPI card or bar that disappears at nought is worse than one showing 0."""
    headers = await _headers(client, normal_user, USER_PASSWORD)
    await _create(client, headers, service="DAS", status="Created")

    body = await _analytics(client, headers)
    assert [row["status"] for row in body["by_status"]] == [s.value for s in TaskStatus]
    assert [row["service"] for row in body["by_service"]] == [s.value for s in TaskService]
    assert {row["count"] for row in body["by_service"]} == {0, 1}


async def test_by_service_carries_the_module_each_bar_links_to(client, normal_user):
    headers = await _headers(client, normal_user, USER_PASSWORD)
    await _create(client, headers, service="DAS")

    body = await _analytics(client, headers)
    modules = {row["service"]: row["module_key"] for row in body["by_service"]}
    assert modules["DAS"] == "DAS_ONBOARDING"
    assert modules["Patch Management"] == "SERVERS"


async def test_counts_span_every_user(client, admin, normal_user):
    """The dashboard is an overview, matching the Task Updates page."""
    admin_headers = await _headers(client, admin, ADMIN_PASSWORD)
    user_headers = await _headers(client, normal_user, USER_PASSWORD)
    await _create(client, admin_headers)
    await _create(client, user_headers)

    assert (await _analytics(client, user_headers))["total"] == 2


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------


async def test_service_filter(client, normal_user):
    headers = await _headers(client, normal_user, USER_PASSWORD)
    await _create(client, headers, service="DAS")
    await _create(client, headers, service="Nexus")

    body = await _analytics(client, headers, "?service=DAS")
    assert body["total"] == 1


async def test_status_filter(client, normal_user):
    headers = await _headers(client, normal_user, USER_PASSWORD)
    await _create(client, headers, status="Triage")
    await _create(client, headers, status="Completed")

    body = await _analytics(client, headers, "?status=Triage")
    assert body["total"] == 1


async def test_date_filter(client, normal_user):
    headers = await _headers(client, normal_user, USER_PASSWORD)
    await _create(client, headers, task_date=str(TODAY))
    await _create(client, headers, task_date=str(YESTERDAY))

    assert (await _analytics(client, headers, f"?date_from={TODAY}&date_to={TODAY}"))["total"] == 1
    assert (await _analytics(client, headers, f"?date_from={YESTERDAY}&date_to={YESTERDAY}"))[
        "total"
    ] == 1


async def test_admin_can_narrow_to_one_user(client, admin, normal_user):
    admin_headers = await _headers(client, admin, ADMIN_PASSWORD)
    user_headers = await _headers(client, normal_user, USER_PASSWORD)
    await _create(client, admin_headers)
    await _create(client, user_headers)

    body = await _analytics(client, admin_headers, f"?user_id={normal_user.id}")
    assert body["total"] == 1
    assert body["recent"][0]["user_id"] == str(normal_user.id)


async def test_user_filter_is_ignored_for_a_normal_user(client, admin, normal_user):
    """The filter is administrative, so asking for it changes nothing."""
    admin_headers = await _headers(client, admin, ADMIN_PASSWORD)
    user_headers = await _headers(client, normal_user, USER_PASSWORD)
    await _create(client, admin_headers)
    await _create(client, user_headers)

    body = await _analytics(client, user_headers, f"?user_id={admin.id}")
    assert body["total"] == 2


async def test_filters_combine(client, admin, normal_user):
    admin_headers = await _headers(client, admin, ADMIN_PASSWORD)
    user_headers = await _headers(client, normal_user, USER_PASSWORD)

    await _create(client, user_headers, service="DAS", status="Inprogress", task_date=str(TODAY))
    await _create(client, user_headers, service="DAS", status="Completed", task_date=str(TODAY))
    await _create(client, user_headers, service="Nexus", status="Inprogress", task_date=str(TODAY))
    await _create(
        client, user_headers, service="DAS", status="Inprogress", task_date=str(YESTERDAY)
    )
    await _create(client, admin_headers, service="DAS", status="Inprogress", task_date=str(TODAY))

    body = await _analytics(
        client,
        admin_headers,
        f"?service=DAS&status=Inprogress&date_from={TODAY}&date_to={TODAY}&user_id={normal_user.id}",
    )
    assert body["total"] == 1
    assert body["recent"][0]["service"] == "DAS"
    assert body["recent"][0]["status"] == "Inprogress"


# ---------------------------------------------------------------------------
# Recent tasks
# ---------------------------------------------------------------------------


async def test_recent_is_newest_first_and_capped(client, normal_user):
    headers = await _headers(client, normal_user, USER_PASSWORD)
    for index in range(12):
        await _create(
            client,
            headers,
            task_date=str(TODAY - timedelta(days=index)),
            description=f"task {index}",
        )

    body = await _analytics(client, headers)
    assert body["total"] == 12
    # A compact panel, not the whole table.
    assert len(body["recent"]) == 8
    assert body["recent"][0]["description"] == "task 0"
    dates = [row["task_date"] for row in body["recent"]]
    assert dates == sorted(dates, reverse=True)


async def test_recent_rows_carry_the_callers_edit_right(client, admin, normal_user):
    admin_headers = await _headers(client, admin, ADMIN_PASSWORD)
    user_headers = await _headers(client, normal_user, USER_PASSWORD)
    await _create(client, admin_headers, description="admin task")

    as_user = await _analytics(client, user_headers)
    assert as_user["recent"][0]["can_edit"] is False

    as_admin = await _analytics(client, admin_headers)
    assert as_admin["recent"][0]["can_edit"] is True


# ---------------------------------------------------------------------------
# Empty and unauthorised
# ---------------------------------------------------------------------------


async def test_empty_database_reports_zeroes_rather_than_failing(client, normal_user):
    headers = await _headers(client, normal_user, USER_PASSWORD)
    body = await _analytics(client, headers)

    assert body["total"] == 0
    assert all(row["count"] == 0 for row in body["by_status"])
    assert all(row["count"] == 0 for row in body["by_service"])
    assert body["recent"] == []


async def test_a_view_only_caller_may_read_analytics(client, guest):
    headers = await _headers(client, guest, GUEST_PASSWORD)
    assert (await client.get("/api/v1/tasks/analytics", headers=headers)).status_code == 200


async def test_analytics_requires_authentication(client):
    assert (await client.get("/api/v1/tasks/analytics")).status_code == 401


# ---------------------------------------------------------------------------
# The "Ongoing" status grouping
# ---------------------------------------------------------------------------


async def test_ongoing_matches_everything_except_completed(client, normal_user):
    headers = await _headers(client, normal_user, USER_PASSWORD)
    for status in ("Created", "Inprogress", "Onhold", "Triage", "Completed"):
        await _create(client, headers, status=status, description=f"a {status} task")

    body = await _analytics(client, headers, "?status=Ongoing")

    assert body["total"] == 4
    assert "Completed" not in {row["description"].split()[1] for row in body["recent"]}
    counts = {row["status"]: row["count"] for row in body["by_status"]}
    assert counts["Completed"] == 0
    assert counts["Created"] == 1
    assert counts["Inprogress"] == 1
    assert counts["Onhold"] == 1
    assert counts["Triage"] == 1


async def test_ongoing_and_completed_partition_the_tasks(client, normal_user):
    headers = await _headers(client, normal_user, USER_PASSWORD)
    for status in ("Created", "Inprogress", "Completed", "Completed", "Triage"):
        await _create(client, headers, status=status)

    everything = (await _analytics(client, headers))["total"]
    ongoing = (await _analytics(client, headers, "?status=Ongoing"))["total"]
    completed = (await _analytics(client, headers, "?status=Completed"))["total"]

    assert ongoing == 3
    assert completed == 2
    assert ongoing + completed == everything


async def test_ongoing_combines_with_the_other_filters(client, normal_user):
    headers = await _headers(client, normal_user, USER_PASSWORD)
    await _create(client, headers, service="DAS", status="Inprogress")
    await _create(client, headers, service="DAS", status="Completed")
    await _create(client, headers, service="Nexus", status="Onhold")

    body = await _analytics(client, headers, "?status=Ongoing&service=DAS")
    assert body["total"] == 1
    assert body["recent"][0]["status"] == "Inprogress"


async def test_ongoing_is_accepted_by_the_task_list_too(client, normal_user):
    """So a dashboard drill-down carrying the grouping still works."""
    headers = await _headers(client, normal_user, USER_PASSWORD)
    await _create(client, headers, status="Completed")
    await _create(client, headers, status="Triage")

    body = (await client.get("/api/v1/tasks?status=Ongoing", headers=headers)).json()
    assert body["total"] == 1
    assert body["items"][0]["status"] == "Triage"


async def test_an_unknown_status_filter_is_rejected(client, normal_user):
    headers = await _headers(client, normal_user, USER_PASSWORD)
    response = await client.get("/api/v1/tasks/analytics?status=Pending", headers=headers)
    assert response.status_code == 422


async def test_options_publish_the_status_filter_values(client, normal_user):
    headers = await _headers(client, normal_user, USER_PASSWORD)
    body = (await client.get("/api/v1/tasks/options", headers=headers)).json()

    assert body["statuses"] == ["Created", "Inprogress", "Onhold", "Completed", "Triage"]
    # The filter offers one more option than a task can actually be in.
    assert body["status_filters"] == [*body["statuses"], "Ongoing"]


# ---------------------------------------------------------------------------
# Recent tasks follow the dashboard filters
# ---------------------------------------------------------------------------


async def test_recent_reflects_every_dashboard_filter(client, admin, normal_user):
    """The panel and the charts must always describe the same set of tasks."""
    admin_headers = await _headers(client, admin, ADMIN_PASSWORD)
    user_headers = await _headers(client, normal_user, USER_PASSWORD)

    await _create(client, user_headers, service="DAS", status="Inprogress", description="keep me")
    await _create(
        client, user_headers, service="DAS", status="Completed", description="wrong status"
    )
    await _create(
        client, user_headers, service="Nexus", status="Inprogress", description="wrong service"
    )
    await _create(
        client, admin_headers, service="DAS", status="Inprogress", description="wrong user"
    )
    await _create(
        client,
        user_headers,
        service="DAS",
        status="Inprogress",
        task_date=str(YESTERDAY),
        description="wrong date",
    )

    body = await _analytics(
        client,
        admin_headers,
        f"?service=DAS&status=Ongoing&date_from={TODAY}&date_to={TODAY}&user_id={normal_user.id}",
    )

    assert [row["description"] for row in body["recent"]] == ["keep me"]
    assert body["total"] == len(body["recent"]) == 1
