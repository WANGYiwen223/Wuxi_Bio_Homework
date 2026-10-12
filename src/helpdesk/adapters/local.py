"""Read adapter for trusted, keyed SQLite demo sources."""

from helpdesk.storage.repository import AccessDenied, Repository


class LocalSources:
    def __init__(self, repository: Repository):
        self.repository = repository

    def employee_context(self, employee_id: str) -> dict:
        employee = self.repository.source("employees", employee_id)
        if employee is None:
            raise AccessDenied("Session employee no longer exists")
        return {
            "employee": {key: employee[key] for key in ["employee_id", "department", "location", "manager_id", "account_status"]},
            "devices": [self.repository.source("devices", device) for device in employee["device_ids"]],
            "accounts": [row for row in self.repository.sources("account_states") if row["employee_id"] == employee_id],
            "access_grants": [row for row in self.repository.sources("access_grants") if row["employee_id"] == employee_id],
        }

    def diagnostics(self, employee_id: str, service_id: str, device_id: str | None) -> list[dict]:
        if device_id:
            device = self.repository.source("devices", device_id)
            if device is None or device["employee_id"] != employee_id:
                raise AccessDenied("Diagnostic target is not assigned to employee")
        return [row for row in self.repository.sources("diagnostic_snapshots") if row["employee_id"] == employee_id and row["service_id"] == service_id and (device_id is None or row["device_id"] == device_id)]
