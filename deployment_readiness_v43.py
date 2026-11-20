"""Offline deployment readiness checks for the VELXTRIA Render entrypoint.

No network, database access, credentials output, or portal imports are performed.
"""
import argparse
import ast
import importlib.util
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

REQUIRED_PACKAGES={"cryptography":"cryptography","psycopg":"psycopg"}
MAINNET_KEYS=("VELXTRIA_BTCPAY_MAINNET_URL","VELXTRIA_BTCPAY_MAINNET_STORE_ID",
              "VELXTRIA_BTCPAY_MAINNET_API_KEY","VELXTRIA_BTCPAY_MAINNET_WEBHOOK_SECRET")

def valid_postgres_url(value):
    """Validate URL structure offline without exposing credentials or connecting."""
    if not isinstance(value, str) or not value or value != value.strip():
        return False
    if any(ord(ch) < 33 or ord(ch) == 127 for ch in value):
        return False
    try:
        parsed = urlsplit(value)
        if parsed.scheme not in ("postgresql", "postgres"):
            return False
        if not parsed.hostname or not parsed.username or not parsed.password:
            return False
        if parsed.port is not None and not (1 <= parsed.port <= 65535):
            return False
        if parsed.query and any(key.lower() in ("password", "pass", "pwd") for key in
                                (part.split("=", 1)[0] for part in parsed.query.split("&"))):
            return False
        return parsed.path in ("", "/") or parsed.path.startswith("/") and len(parsed.path) > 1
    except (ValueError, TypeError):
        return False

def inspect(root, environ=None, finder=None):
    root=Path(root)
    env=os.environ if environ is None else environ
    find=importlib.util.find_spec if finder is None else finder
    checks=[]
    def add(name,ok,detail):
        checks.append({"check":name,"ok":bool(ok),"detail":detail})
    portal=root/"portal.py"
    if not portal.is_file():
        add("entrypoint",False,"portal.py is missing")
    else:
        try:
            tree=ast.parse(portal.read_text(encoding="utf-8"),filename=str(portal))
            add("entrypoint",True,"portal.py parses")
            local=set()
            for node in tree.body:
                if isinstance(node,ast.Import):
                    local.update(alias.name.split(".")[0] for alias in node.names)
                elif isinstance(node,ast.ImportFrom) and node.module:
                    local.add(node.module.split(".")[0])
            missing=sorted(name for name in local if
                           (root/(name+".py")).is_file() is False and
                           (root/name/"__init__.py").is_file() is False and
                           name not in getattr(__import__("sys"),"stdlib_module_names",set()) and
                           name not in REQUIRED_PACKAGES and
                           name not in ("typing_extensions",))
            # The entrypoint's imports are expected to be local or standard-library.
            add("local_imports",not missing,
                "All direct non-standard entrypoint imports have local modules" if not missing
                else "Missing local modules: "+", ".join(missing))
        except (OSError,SyntaxError,UnicodeError) as exc:
            add("entrypoint",False,type(exc).__name__+" while parsing portal.py")
    requirements=root/"requirements.txt"
    declared=requirements.read_text(encoding="utf-8") if requirements.is_file() else ""
    for name,package in REQUIRED_PACKAGES.items():
        present=any(line.strip().lower().startswith(package.lower()+suffix)
                    for line in declared.splitlines()
                    for suffix in (">","=","<","["," ","~","!"))
        add("requirements_"+name,present,
            package+" declared in requirements.txt" if present else package+" missing from requirements.txt")
        try:installed=find(name) is not None
        except (ImportError,ValueError,AttributeError):installed=False
        add("installed_"+name,installed,
            package+" import location found" if installed else package+" is not installed")
    # Render's free filesystem is ephemeral. Fail the deployment before
    # accepting real customers without a durable database and report store.
    durable=env.get("VELXTRIA_REQUIRE_PERSISTENCE","0")=="1"
    render=env.get("VELXTRIA_DEPLOYMENT_MODE","local")=="render-preview"
    if render:
        add("render_persistence_enforced",durable,
            "Render persistence enforcement enabled" if durable else
            "Render must set VELXTRIA_REQUIRE_PERSISTENCE=1")
    if durable or render:
        database=env.get("VELXTRIA_DATABASE_URL","").strip()
        add("durable_database",valid_postgres_url(database),
            "PostgreSQL URL structure valid (connectivity not checked)" if valid_postgres_url(database) else
            "Persistent mode requires a valid PostgreSQL URL (host, user, password, database)")
        storage=bool(env.get("VELXTRIA_SUPABASE_URL","").strip() and
                     env.get("VELXTRIA_SUPABASE_SERVICE_KEY","").strip())
        add("private_report_storage",storage,
            "Private report storage configured" if storage else
            "Persistent mode requires Supabase URL and service key for report downloads")
    enabled=env.get("VELXTRIA_ENABLE_BTCPAY_MAINNET_CHECKOUT","0")=="1"
    if enabled:
        missing=[key for key in MAINNET_KEYS if not env.get(key,"").strip()]
        add("mainnet_configuration",not missing,
            "Mainnet checkout configured" if not missing else "Mainnet enabled but missing: "+", ".join(missing))
        url=env.get("VELXTRIA_BTCPAY_MAINNET_URL","")
        from urllib.parse import urlsplit
        host=urlsplit(url).hostname
        add("mainnet_host",url.startswith("https://") and bool(host) and
            host not in ("localhost","127.0.0.1") and not (host or "").startswith("testnet."),
            "Mainnet URL has an HTTPS non-testnet host" if url.startswith("https://") and host and not host.startswith("testnet.") else "Mainnet requires HTTPS non-testnet host")
    else:
        add("mainnet_configuration",True,"Mainnet checkout disabled (safe default)")
    return {"ready":all(item["ok"] for item in checks),"checks":checks}

def main(argv=None):
    parser=argparse.ArgumentParser(description="VELXTRIA offline deployment readiness")
    parser.add_argument("--root",default=str(Path(__file__).resolve().parent))
    parser.add_argument("--json",action="store_true")
    args=parser.parse_args(argv)
    report=inspect(args.root)
    if args.json:print(json.dumps(report,indent=2))
    else:
        for check in report["checks"]:
            print(("[PASS] " if check["ok"] else "[FAIL] ")+check["check"]+": "+check["detail"])
        print("Deployment readiness:", "PASS" if report["ready"] else "FAIL")
    return 0 if report["ready"] else 1

if __name__=="__main__":
    raise SystemExit(main())
