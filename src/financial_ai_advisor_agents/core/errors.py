class AdvisorError(Exception):
    pass


class StructuredOutputError(AdvisorError):
    pass


class SQLValidationError(AdvisorError):
    pass


class CapabilityError(AdvisorError):
    pass
