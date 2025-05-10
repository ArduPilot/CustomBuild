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


class VehiclesManager:
    __singleton = None

    def __init__(self) -> None:
        # Enforce singleton pattern by raising an error if
        # an instance already exists.
        if VehiclesManager.__singleton:
            raise RuntimeError("VehiclesManager must be a singleton.")

        self.vehicles = set()
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
