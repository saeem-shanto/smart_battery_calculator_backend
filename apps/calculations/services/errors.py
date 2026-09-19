class CalculationEngineError(RuntimeError):
    """Base class for configured calculation-engine failures."""


class CalculationEngineUnavailable(CalculationEngineError):
    """The selected engine cannot be started or is not installed."""


class CalculationEngineExecutionError(CalculationEngineError):
    """The selected engine started but failed to produce a valid result."""
