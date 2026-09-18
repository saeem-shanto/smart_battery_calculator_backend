from django.conf import settings


def get_engine():
    """Return the explicitly configured engine. Never silently fall back."""
    if settings.CALCULATION_ENGINE == "octave":
        # Lazy imports matter on small instances: selecting Octave should not load
        # NumPy/SciPy simply because the Django process starts.
        from .octave_engine import OctaveEngine

        return OctaveEngine()
    if settings.CALCULATION_ENGINE == "matlab_compiled":
        from .matlab_compiled import MatlabCompiledEngine

        return MatlabCompiledEngine()
    if settings.CALCULATION_ENGINE == "reference_python":
        from .reference_engine import ReferencePythonEngine

        return ReferencePythonEngine()
    raise RuntimeError(f"Unsupported CALCULATION_ENGINE={settings.CALCULATION_ENGINE!r}")
