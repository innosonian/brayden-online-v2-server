from enum import Enum


class ExceptionType(Enum):
    NOT_FOUND = 1
    INVALID_TOKEN = 2
    INVALID_PERMISSION = 3
    NOT_MATCHED = 4
    INCORRECT_FORMAT = 5


class GetException(Exception):
    def __init__(self, message, exception_type):
        super().__init__()
        self.message = message
        self.exception_type = exception_type


class GetExceptionWithStatuscode(GetException):
    def __init__(self, status_code, message, exception_type):
        super().__init__(message, exception_type)
        self.status_code = status_code
