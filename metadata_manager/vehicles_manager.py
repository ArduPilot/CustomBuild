class Vehicle:
    def __init__(self,
                 id: str,
                 name: str,
                 ap_source_subdir: str,
                 fw_server_vehicle_sdir: str,
                 waf_build_command: str,
                 ) -> None:
        self.id = id
        self.name = name
        self.ap_source_subdir = ap_source_subdir
        self.fw_server_vehicle_sdir = fw_server_vehicle_sdir
        self.waf_build_command = waf_build_command

    def __eq__(self, other):
        if isinstance(other, Vehicle):
            return self.id == other.id
        return False

    def __hash__(self):
        return hash(self.id)


# Default vehicles configuration
DEFAULT_VEHICLES = [
    Vehicle(
        id="copter",
        name="Copter",
        ap_source_subdir="ArduCopter",
        fw_server_vehicle_sdir="Copter",
        waf_build_command="copter"
    ),
    Vehicle(
        id="plane",
        name="Plane",
        ap_source_subdir="ArduPlane",
        fw_server_vehicle_sdir="Plane",
        waf_build_command="plane"
    ),
    Vehicle(
        id="rover",
        name="Rover",
        ap_source_subdir="Rover",
        fw_server_vehicle_sdir="Rover",
        waf_build_command="rover"
    ),
    Vehicle(
        id="sub",
        name="Sub",
        ap_source_subdir="ArduSub",
        fw_server_vehicle_sdir="Sub",
        waf_build_command="sub"
    ),
    Vehicle(
        id="heli",
        name="Heli",
        ap_source_subdir="ArduCopter",
        fw_server_vehicle_sdir="Copter",
        waf_build_command="heli"
    ),
    Vehicle(
        id="blimp",
        name="Blimp",
        ap_source_subdir="Blimp",
        fw_server_vehicle_sdir="Blimp",
        waf_build_command="blimp"
    ),
    Vehicle(
        id="tracker",
        name="Tracker",
        ap_source_subdir="AntennaTracker",
        fw_server_vehicle_sdir="AntennaTracker",
        waf_build_command="antennatracker"
    ),
    Vehicle(
        id="ap-periph",
        name="AP_Periph",
        ap_source_subdir="Tools/AP_Periph",
        fw_server_vehicle_sdir="AP_Periph",
        waf_build_command="AP_Periph"
    ),
]


class VehiclesManager:
    __singleton = None

    def __init__(self, vehicles: list = DEFAULT_VEHICLES) -> None:
        """
        Initialize VehiclesManager with a list of vehicles.

        Args:
            vehicles: List of Vehicle objects. Defaults to DEFAULT_VEHICLES.
        """
        # Enforce singleton pattern by raising an error if
        # an instance already exists.
        if VehiclesManager.__singleton:
            raise RuntimeError("VehiclesManager must be a singleton.")

        self.vehicles = set(vehicles)

        VehiclesManager.__singleton = self

    def get_all_vehicles(self) -> frozenset:
        return frozenset(self.vehicles)

    def add_vehicle(self, vehicle: Vehicle) -> None:
        return self.vehicles.add(vehicle)

    def get_vehicle_by_id(self, vehicle_id: str) -> Vehicle:
        if vehicle_id is None:
            raise ValueError("vehicle_id is a required parameter.")

        return next(
            (
                vehicle for vehicle in self.get_all_vehicles()
                if vehicle.id == vehicle_id
            ),
            None
        )

    @staticmethod
    def get_singleton() -> "VehiclesManager":
        return VehiclesManager.__singleton
