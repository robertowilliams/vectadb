from shortid.config import load_config
from shortid.rpc_server import run_rpc_server

if __name__ == "__main__":
    load_config()  # optional: to trigger config loading/logging
    run_rpc_server()
