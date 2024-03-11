from enum import Enum

class ExceptionType(Enum):
    NOT_FOUND = 1
    INVALID_TOKEN = 2
    INVALID_PERMISSION = 3


class GetException(Exception):
    def __init__(self, message, exception_type):
        super().__init__(self)
        self.message = message
        self.exception_type = exception_type
