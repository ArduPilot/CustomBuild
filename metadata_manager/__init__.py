from .versions_fetcher import (
    VersionsFetcher,
    RemoteInfo,
)

from .ap_src_meta_fetcher import (
    APSourceMetadataFetcher,
)

from .vehicles_manager import (
    VehiclesManager,
    Vehicle,
)

__all__ = [
    "APSourceMetadataFetcher",
    "VersionsFetcher",
    "RemoteInfo",
    "VehiclesManager",
    "Vehicle",
]

vehicles_manager = VehiclesManager()

vehicles_manager.add_vehicle(
    Vehicle(
        name="Copter",
        waf_build_command="copter"
    )
)

vehicles_manager.add_vehicle(
    Vehicle(
        name="Plane",
        waf_build_command="plane"
    )
)

vehicles_manager.add_vehicle(
    Vehicle(
        name="Rover",
        waf_build_command="rover"
    )
)

vehicles_manager.add_vehicle(
    Vehicle(
        name="Sub",
        waf_build_command="sub"
    )
)

vehicles_manager.add_vehicle(
    Vehicle(
        name="Heli",
        waf_build_command="heli"
    )
)

vehicles_manager.add_vehicle(
    Vehicle(
        name="Blimp",
        waf_build_command="blimp"
    )
)

vehicles_manager.add_vehicle(
    Vehicle(
        name="Tracker",
        waf_build_command="AntennaTracker"
    )
)

vehicles_manager.add_vehicle(
    Vehicle(
        name="AP_Periph",
        waf_build_command="AP_Periph"
    )
)
