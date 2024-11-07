class MetadataManagerException(Exception):
    pass


class TooManyInstancesError(MetadataManagerException):
    def __init__(self, name: str):
        message = f"{name} should be a singleton."
        super().__init__(message)
