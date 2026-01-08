import os
import yaml
from nebula3.gclient.net import ConnectionPool
from nebula3.Config import Config as NebulaConfig

project_root = os.path.abspath(os.path.dirname(__file__))
config_path = os.path.join(project_root, "config", "config.yaml")

with open(config_path, "r") as f:
    config = yaml.safe_load(f)

NEBULA_HOST = config["nebula"]["graphd_host"]
NEBULA_PORT = config["nebula"]["graphd_port"]
NEBULA_USER = config["nebula"]["user"]
NEBULA_PASSWORD = config["nebula"]["password"]
NEBULA_SPACE = config["nebula"].get("space", "agent_registry")

print(f"Trying to connect to {NEBULA_HOST}:{NEBULA_PORT} as {NEBULA_USER}, space={NEBULA_SPACE}")

nebula_conf = NebulaConfig()
nebula_conf.max_connection_pool_size = 5

pool = ConnectionPool()
ok = pool.init([(NEBULA_HOST, NEBULA_PORT)], nebula_conf)
print("Pool init result:", ok)
if not ok:
    raise RuntimeError("Failed to init Nebula connection pool")

with pool.session_context(NEBULA_USER, NEBULA_PASSWORD) as session:
    res = session.execute("SHOW SPACES;")
    print("SHOW SPACES succeeded?:", res.is_succeeded())
    if not res.is_succeeded():
        print("Error:", res.error_msg())
    else:
        for row in res.rows():
            print("SPACE:", row.values[0].as_string())

    # Try to USE your space
    print(f"\nTrying: USE {NEBULA_SPACE};")
    use_res = session.execute(f"USE {NEBULA_SPACE};")
    print("USE succeeded?:", use_res.is_succeeded())
    if not use_res.is_succeeded():
        print("Error:", use_res.error_msg())
