class Vehicle:
    def __init__(self,
                 name: str,
                 waf_build_command: str,
                 ) -> None:
        self.name = name
        self.waf_build_command = waf_build_command

    def __eq__(self, other):
        if isinstance(other, Vehicle):
            return self.name == other.name
        return False

    def __hash__(self):
        return hash(self.name)


# Default vehicles configuration
DEFAULT_VEHICLES = [
    Vehicle(name="Copter", waf_build_command="copter"),
    Vehicle(name="Plane", waf_build_command="plane"),
    Vehicle(name="Rover", waf_build_command="rover"),
    Vehicle(name="Sub", waf_build_command="sub"),
    Vehicle(name="Heli", waf_build_command="heli"),
    Vehicle(name="Blimp", waf_build_command="blimp"),
    Vehicle(name="Tracker", waf_build_command="antennatracker"),
    Vehicle(name="AP_Periph", waf_build_command="AP_Periph"),
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

    def get_all_vehicle_names_sorted(self) -> list:
        return sorted([v.name for v in self.vehicles])

    def get_all_vehicles(self) -> frozenset:
        return frozenset(self.vehicles)

    def add_vehicle(self, vehicle: Vehicle) -> None:
        return self.vehicles.add(vehicle)

    def get_vehicle_from_name(self, vehicle_name: str) -> Vehicle:
        if vehicle_name is None:
            raise ValueError("vehicle_name is a required parameter.")

        return next(
            (
                vehicle for vehicle in self.get_all_vehicles()
                if vehicle.name == vehicle_name
            ),
            None
        )

    @staticmethod
    def get_singleton() -> "VehiclesManager":
        return VehiclesManager.__singleton
