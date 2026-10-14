"""Read adapter for trusted, keyed SQLite demo sources."""

from helpdesk.storage.repository import AccessDenied, Repository


class LocalSources:
    def __init__(self, repository: Repository):
        self.repository = repository

    @staticmethod
    def can_read_resource(employee: dict, resource: dict) -> bool:
        scope = resource.get("diagnostic_readers", {})
        return employee["account_status"] == "active" and (
            employee["department"] in scope.get("departments", [])
            or bool(set(employee["roles"]) & set(scope.get("roles", [])))
        )

    def employee_context(self, employee_id: str) -> dict:
        employee = self.repository.source("employees", employee_id)
        if employee is None:
            raise AccessDenied("Session employee no longer exists")
        return {
            "employee": {key: employee[key] for key in ["employee_id", "department", "roles", "location", "manager_id", "account_status"]},
            "devices": [self.repository.source("devices", device) for device in employee["device_ids"]],
            "accounts": [row for row in self.repository.sources("account_states") if row["employee_id"] == employee_id],
            "access_grants": [row for row in self.repository.sources("access_grants") if row["employee_id"] == employee_id],
            "diagnostic_resources": [row for row in self.repository.sources("resources") if self.can_read_resource(employee, row)],
        }

    def diagnostics(self, employee_id: str, service_id: str, device_id: str | None, resource_id: str | None = None) -> list[dict]:
        if device_id and resource_id:
            raise ValueError("Choose a personal device or shared resource")
        employee = self.repository.source("employees", employee_id)
        if employee is None:
            raise AccessDenied("Session employee no longer exists")
        if device_id:
            device = self.repository.source("devices", device_id)
            if device is None or device["employee_id"] != employee_id:
                raise AccessDenied("Diagnostic target is not assigned to employee")
        resources = {r["resource_id"]: r for r in self.repository.sources("resources")}
        if resource_id:
            resource = resources.get(resource_id)
            if not resource or resource["service_id"] != service_id or not self.can_read_resource(employee, resource):
                raise AccessDenied("Shared diagnostic resource is not accessible")
        rows = []
        for row in self.repository.sources("diagnostic_snapshots"):
            if row["service_id"] != service_id:
                continue
            if row["employee_id"] == employee_id and not resource_id and (device_id is None or row["device_id"] == device_id):
                rows.append(row)
            elif row["employee_id"] is None and not device_id:
                resource = resources.get(row.get("resource_id"))
                if resource and resource["service_id"] == service_id and (resource_id is None or row["resource_id"] == resource_id) and self.can_read_resource(employee, resource):
                    rows.append(row)
        return rows
