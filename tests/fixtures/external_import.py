import os
import json


def uses_external():
    path = os.path.join("a", "b")
    return json.dumps({"path": path})
