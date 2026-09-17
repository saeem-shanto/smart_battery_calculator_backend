from django.conf import settings
from .reference_engine import ReferencePythonEngine
from .matlab_http import MatlabHttpEngine

def get_engine():
    if settings.CALCULATION_ENGINE=="reference_python": return ReferencePythonEngine()
    if settings.CALCULATION_ENGINE=="matlab_http": return MatlabHttpEngine()
    raise RuntimeError(f"Unsupported CALCULATION_ENGINE={settings.CALCULATION_ENGINE!r}")
