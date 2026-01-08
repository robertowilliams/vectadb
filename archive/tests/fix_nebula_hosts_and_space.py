import os
import time
import yaml
from nebula3.gclient.net import ConnectionPool
from nebula3.Config import Config as NebulaConfig

# ------- load config -------
project_root = os.path.abspath(os.path.dirname(__file__))
config_path = os.path.join(project_root, "config", "config.yaml")

with open(config_path, "r") as f:
    config = yaml.safe_load(f)

NEBULA_HOST = config["nebula"]["graphd_host"]
NEBULA_PORT = config["nebula"]["graphd_port"]
NEBULA_USER = config["nebula"]["user"]
NEBULA_PASSWORD = config["nebula"]["password"]
NEBULA_SPACE = config["nebula"].get("space", "agent_registry")

# ⚠️ Storage RPC port: default is 9779 for a single-node install.
# If you customized nebula-storaged.conf, change this to that port.
STORAGE_IP = "127.0.0.1"
STORAGE_PORT = 9779

print(f"Connecting to {NEBULA_HOST}:{NEBULA_PORT} as {NEBULA_USER}")
nebula_conf = NebulaConfig()
nebula_conf.max_connection_pool_size = 5

pool = ConnectionPool()
ok = pool.init([(NEBULA_HOST, NEBULA_PORT)], nebula_conf)
print("Pool init:", ok)
if not ok:
    raise RuntimeError("Failed to init Nebula pool")

with pool.session_context(NEBULA_USER, NEBULA_PASSWORD) as session:
    # 1) Show existing hosts
    print("\n== SHOW HOSTS before ADD HOSTS ==")
    res = session.execute("SHOW HOSTS;")
    print("SHOW HOSTS succeeded?:", res.is_succeeded())
    if res.is_succeeded():
        for row in res.rows():
            # columns: Host, Port, Status, Leader count, etc. depending on version
            vals = [v.as_string() if hasattr(v, "as_string") else str(v) for v in row.values]
            print("  ", vals)
    else:
        print("SHOW HOSTS error:", res.error_msg())

    # 2) Try to ADD HOSTS (only makes sense for single-node/local setups)
    add_stmt = f'ADD HOSTS "{STORAGE_IP}":{STORAGE_PORT};'
    print("\nExecuting:", add_stmt)
    add_res = session.execute(add_stmt)
    print("ADD HOSTS succeeded?:", add_res.is_succeeded())
    if not add_res.is_succeeded():
        print("ADD HOSTS error:", add_res.error_msg())
        print("\n⚠ If this fails, check nebula-storaged.conf for the correct IP/port "
              "and update STORAGE_IP/STORAGE_PORT in this script.")
        exit(1)

    # 3) Wait one heartbeat so meta and storage sync (default heartbeat is 10s)
    print("\nWaiting ~12 seconds for heartbeat...")
    time.sleep(12)

    # 4) Check hosts again
    print("\n== SHOW HOSTS after ADD HOSTS ==")
    res2 = session.execute("SHOW HOSTS;")
    print("SHOW HOSTS succeeded?:", res2.is_succeeded())
    if res2.is_succeeded():
        for row in res2.rows():
            vals = [v.as_string() if hasattr(v, "as_string") else str(v) for v in row.values]
            print("  ", vals)
    else:
        print("SHOW HOSTS error:", res2.error_msg())

    # 5) Try to create the space
    create_stmt = (
        f"CREATE SPACE IF NOT EXISTS {NEBULA_SPACE}("
        "partition_num = 16, replica_factor = 1, vid_type = FIXED_STRING(64));"
    )
    print("\nExecuting:", create_stmt)
    create_res = session.execute(create_stmt)
    print("CREATE SPACE succeeded?:", create_res.is_succeeded())
    if not create_res.is_succeeded():
        print("CREATE SPACE error:", create_res.error_msg())

    # 6) Try USE space
    print(f"\nTrying: USE {NEBULA_SPACE};")
    use_res = session.execute(f"USE {NEBULA_SPACE};")
    print("USE succeeded?:", use_res.is_succeeded())
    if not use_res.is_succeeded():
        print("USE error:", use_res.error_msg())
    else:
        print("\n✅ Space is ready and usable.")
