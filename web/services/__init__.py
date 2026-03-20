"""
Business logic services for the application.
"""
from web.services.vehicles import get_vehicles_service, VehiclesService
from web.services.builds import get_builds_service, BuildsService
from web.services.admin import get_admin_service, AdminService

__all__ = [
    "get_vehicles_service",
    "VehiclesService",
    "get_builds_service",
    "BuildsService",
    "get_admin_service",
    "AdminService",
]
