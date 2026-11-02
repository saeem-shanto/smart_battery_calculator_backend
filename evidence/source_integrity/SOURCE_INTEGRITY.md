# Client MATLAB Source Integrity

The following files are client-owned legacy source and must not be renamed or edited:

| File | Packaged byte size | SHA-256 |
| --- | ---: | --- |
| `battrail.m` | 2289 | `536383fe9ffe6a248f0970789ada00b791b2554445ccc64cdf14a73617f808bf` |
| `natpaymenttrail.m` | 3255 | `6898b5d4fad5f4ed27fbb0de6e409a3d0db5c655b60aae75678b755a5bb5a631` |
| `rpresults.m` | 620 | `a50f78d4570b0f82d13fe0c3be6fd5d4408747104412a86228b74bbdd4fc48e6` |

These hashes are for the source snapshots packaged with this backend. `OctaveEngine.status()` reports per-file hashes and a combined algorithm hash at runtime.

The web compatibility bridge is deliberately stored separately under `octave_bridge/`.

Runtime execution calls `natpaymenttrail.m`; that script invokes `battrail.m`. `rpresults.m` is retained unchanged as part of the client source set but is not invoked by the web request because it is a plotting/legacy result-reading script.
