import enum, uuid, base64
from dataclasses import is_dataclass, asdict
from decimal     import Decimal
from datetime    import datetime, date
from pathlib     import Path
from typing      import Any
import numpy as np
import pandas as pd

JSONSafe: Any = lambda value: (
    value                         if value is None                                                      # None → None
    else value                    if isinstance(value, (str, int, float, bool))                         # Basic types → already JSON safe
    else value.isoformat()        if isinstance(value, (date, datetime))                                # Datetime-like → ISO8601 string
    else str(value)               if isinstance(value, uuid.UUID)                                       # UUID → string
    else value.value              if isinstance(value, enum.Enum)                                       # Enum → value or .name
    else list(value)              if isinstance(value, set)                                             # Set → list
    else str(value)               if isinstance(value, Path)                                            # Paths → string
    else float(value)             if isinstance(value, Decimal)                                         # Decimal → float
    else {"real": value.real, "imag": value.imag} if isinstance(value, complex)                         # complex → dict
    else base64.b64encode(value).decode('utf-8') if isinstance(value, (bytes, bytearray))               # Bytes → base64
    else JSONSafe(value.tolist()) if isinstance(value, np.ndarray)                                      # Numpy Array → process values
    else JSONSafe(value.item())   if isinstance(value, np.generic)                                      # Numpy Number → process values
    else {f: JSONSafe(getattr(value, f)) for f in value._fields} if isinstance(value, tuple) and hasattr(value, "_fields") # Named Tuples
    else [JSONSafe(v) for v in value] if isinstance(value, (list, tuple))                               # List/tuple → process each element
    else {k:JSONSafe(v) for k,v in value.items()} if isinstance(value, dict)                            # Dict → process values
    else [JSONSafe(row) for row in value.to_dict(orient="records")] if isinstance(value, pd.DataFrame)  # Dataframe → Safe Rows
    else {k:JSONSafe(v) for k,v in value.to_dict().items()} if isinstance(value, pd.Series)             # Series → process values
    else JSONSafe(asdict(value)) if is_dataclass(value)                                                 # Dataclass → dict
    else {k:JSONSafe(v) for k,v in vars(value).items()} if hasattr(value, "__dict__")                   # (Fallback) Use a safe dict if able
    else JSONSafe(value.__json__()) if hasattr(value, '__json__')                                       # (Fallback) JSONSafe JSON if available
    else repr(value) # (Fallback - All obj. have repr str)
)