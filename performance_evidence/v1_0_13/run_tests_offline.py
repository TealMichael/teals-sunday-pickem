"""Run an unchanged source tree's suite with outbound sockets blocked."""
import json
import os
from pathlib import Path
import socket
import sys

source = Path(sys.argv[1]).resolve()
output = Path(sys.argv[2]).resolve()
attempts = []

def blocked(*args, **kwargs):
    attempts.append("blocked outbound socket operation")
    raise AssertionError("External network disabled for performance baseline")

socket.socket.connect = blocked
socket.socket.connect_ex = blocked
socket.create_connection = blocked
socket.getaddrinfo = blocked
os.environ["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"
os.chdir(source)
sys.path.insert(0, str(source))
import pytest

code = pytest.main(["-q", "-p", "no:cacheprovider", "--junitxml=" + str(output)])
print(json.dumps({"python": sys.version, "pytest_exit": int(code),
                  "blocked_network_attempts": len(attempts)}))
raise SystemExit(code if code else bool(attempts))
