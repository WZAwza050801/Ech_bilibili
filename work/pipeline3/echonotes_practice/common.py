import hashlib
import json
import os
import subprocess
from pathlib import Path


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def save_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def digest(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def run(argv, timeout=300, **kwargs):
    result = subprocess.run([str(x) for x in argv], capture_output=True, timeout=timeout, **kwargs)
    if result.returncode:
        raise RuntimeError(f"{Path(str(argv[0])).name} failed ({result.returncode}): "
                           + result.stderr.decode("utf-8", "replace")[-2000:])
    return result


def stamp(t):
    minute, second = divmod(int(t), 60)
    return f"{minute:02d}:{second:02d}"
