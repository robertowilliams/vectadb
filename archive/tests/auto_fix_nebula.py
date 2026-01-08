import os
import time
import yaml
from urllib.request import urlopen

from nebula3.gclient.net import ConnectionPool
from nebula3.Config import Config as NebulaConfig

"""
auto_fix_nebula.py

- Reads config/config.yaml to get nebula graphd connection.
- Calls storaged HTTP /flags to discover local_ip and port.
- Issues ADD HOSTS "<local_ip>":port;
- Waits a bit, shows hosts, then tries to CREATE SPACE and USE it.
"""

project_root = os.path.abspath(os.path.dirname(__file__))
config_path = os.path.join(project_root, "config", "config.yaml")

with open(config_path, "r") as f:
    config = yaml.safe_load(f)

NEBULA_HOST = config["nebula"]["graphd_host"]
NEBULA_PORT = config["nebula"]["graphd_port"]
NEBULA_USER = config["nebula"]["user"]
NEBULA_PASSWORD = config["nebula"]["password"]
NEBULA_SPACE = config["nebula"].get("space", "agent_registry")

# We assume storaged HTTP is mapped on the same host as graphd, port 19779 (Nebula default).
STORAGE_HTTP_PORT = 19779

def discover_storage_flags():
    url = f"http://{NEBULA_HOST}:{STORAGE_HTTP_PORT}/flags"
    print(f"Fetching storaged flags from {url}")
    with urlopen(url, timeout=5) as resp:
        text = resp.read().decode("utf-8", errors="ignore")
    local_ip = None
    port = None
    meta_addrs = None
    for line in text.splitlines():
        line = line.strip()
        if "local_ip" in line and "=" in line:
            parts = line.split("=", 1)
            if parts[0].endswith("local_ip"):
                local_ip = parts[1].strip()
        if "meta_server_addrs" in line and "=" in line:
            parts = line.split("=", 1)
            if parts[0].endswith("meta_server_addrs"):
                meta_addrs = parts[1].strip()
        # heuristic for primary RPC port: look for a line ending in "port"
        if "port=" in line and "metrics" not in line and "ws_http" not in line and "http_port" not in line:
            parts = line.split("=", 1)
            if parts[0].endswith("port"):
                try:
                    port = int(parts[1].strip())
                except ValueError:
                    pass
    return local_ip, port, meta_addrs

def main():
    print(f"Connecting to graphd {NEBULA_HOST}:{NEBULA_PORT} as {NEBULA_USER}")
    nebula_conf = NebulaConfig()
    nebula_conf.max_connection_pool_size = 5

    pool = ConnectionPool()
    ok = pool.init([(NEBULA_HOST, NEBULA_PORT)], nebula_conf)
    print("Pool init:", ok)
    if not ok:
        raise RuntimeError("Failed to init Nebula pool")

    local_ip, storage_port, meta_addrs = discover_storage_flags()
    print(f"Discovered storaged local_ip={local_ip}, port={storage_port}, meta_server_addrs={meta_addrs}")

    if not local_ip or not storage_port:
        print("❌ Could not parse storaged local_ip/port from /flags; aborting.")
        return

    with pool.session_context(NEBULA_USER, NEBULA_PASSWORD) as session:
        print("\n== SHOW HOSTS before ADD HOSTS ==")
        res = session.execute("SHOW HOSTS;")
        print("SHOW HOSTS succeeded?:", res.is_succeeded())
        if res.is_succeeded():
            for row in res.rows():
                vals = [v.as_string() if hasattr(v, "as_string") else str(v) for v in row.values]
                print("  ", vals)
        else:
            print("SHOW HOSTS error:", res.error_msg())

        add_stmt = f'ADD HOSTS "{local_ip}":{storage_port};'
        print("\nExecuting:", add_stmt)
        add_res = session.execute(add_stmt)
        print("ADD HOSTS succeeded?:", add_res.is_succeeded())
        if not add_res.is_succeeded():
            print("ADD HOSTS error:", add_res.error_msg())
            return

        print("\nWaiting ~12 seconds for heartbeat...")
        time.sleep(12)

        print("\n== SHOW HOSTS after ADD HOSTS ==")
        res2 = session.execute("SHOW HOSTS;")
        print("SHOW HOSTS succeeded?:", res2.is_succeeded())
        if res2.is_succeeded():
            for row in res2.rows():
                vals = [v.as_string() if hasattr(v, "as_string") else str(v) for v in row.values]
                print("  ", vals)
        else:
            print("SHOW HOSTS error:", res2.error_msg())

        create_stmt = (
            f"CREATE SPACE IF NOT EXISTS {NEBULA_SPACE}("
            "partition_num = 16, replica_factor = 1, vid_type = FIXED_STRING(64));"
        )
        print("\nExecuting:", create_stmt)
        create_res = session.execute(create_stmt)
        print("CREATE SPACE succeeded?:", create_res.is_succeeded())
        if not create_res.is_succeeded():
            print("CREATE SPACE error:", create_res.error_msg())

        print(f"\nTrying: USE {NEBULA_SPACE};")
        use_res = session.execute(f"USE {NEBULA_SPACE};")
        print("USE succeeded?:", use_res.is_succeeded())
        if not use_res.is_succeeded():
            print("USE error:", use_res.error_msg())
        else:
            print("\n✅ Space is ready and usable.")

if __name__ == "__main__":
    main()
