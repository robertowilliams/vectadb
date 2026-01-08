import os
import yaml
from nebula3.gclient.net import ConnectionPool
from nebula3.Config import Config as NebulaConfig

# Load config.yaml
project_root = os.path.abspath(os.path.dirname(__file__))
config_path = os.path.join(project_root, "config", "config.yaml")

with open(config_path, "r") as f:
    config = yaml.safe_load(f)

NEBULA_HOST = config["nebula"]["graphd_host"]
NEBULA_PORT = config["nebula"]["graphd_port"]
NEBULA_USER = config["nebula"]["user"]
NEBULA_PASSWORD = config["nebula"]["password"]
NEBULA_SPACE = config["nebula"].get("space", "agent_registry")

print(f"Connecting to {NEBULA_HOST}:{NEBULA_PORT} as {NEBULA_USER}")
print(f"Target space: {NEBULA_SPACE}")

nebula_conf = NebulaConfig()
nebula_conf.max_connection_pool_size = 5

pool = ConnectionPool()
ok = pool.init([(NEBULA_HOST, NEBULA_PORT)], nebula_conf)
print("Pool init:", ok)
if not ok:
    raise RuntimeError("Failed to init Nebula pool")

with pool.session_context(NEBULA_USER, NEBULA_PASSWORD) as session:
    # Show existing spaces
    res = session.execute("SHOW SPACES;")
    print("SHOW SPACES succeeded?:", res.is_succeeded())
    if res.is_succeeded():
        print("Existing spaces:")
        for row in res.rows():
            print("  -", row.values[0].as_string())
    else:
        print("SHOW SPACES error:", res.error_msg())

    # Create the space if it doesn't exist
    create_stmt = (
        f"CREATE SPACE IF NOT EXISTS {NEBULA_SPACE}("
        "partition_num = 16, replica_factor = 1, vid_type = FIXED_STRING(64));"
    )
    print("\nExecuting:", create_stmt)
    create_res = session.execute(create_stmt)
    print("CREATE SPACE succeeded?:", create_res.is_succeeded())
    if not create_res.is_succeeded():
        print("CREATE SPACE error:", create_res.error_msg())

    # Try to USE the space
    use_res = session.execute(f"USE {NEBULA_SPACE};")
    print("\nUSE", NEBULA_SPACE, "succeeded?:", use_res.is_succeeded())
    if not use_res.is_succeeded():
        print("USE error:", use_res.error_msg())
    else:
        print("Space is ready.")
