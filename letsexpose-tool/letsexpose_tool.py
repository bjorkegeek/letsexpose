import argparse
import os
import re
import sys
from subprocess import call

import yaml


class ToolError(Exception):
    def __init__(self, message, exit_code=2):
        super(ToolError, self).__init__(message, exit_code)
        self.message = message
        self.exit_code = exit_code


def parse_args():
    parser = argparse.ArgumentParser(description="the letsexpose tool")
    parser.add_argument("config_file", type=str, help="YAML configuration file")
    parser.add_argument(
        "task", choices=["certbot-init", "update-nginx"], help="The task to execute"
    )
    return parser.parse_args()


def load_config(filename):
    with open(filename) as f:
        return yaml.safe_load(f)


def validate_dict(dictobj):
    if not isinstance(dictobj, dict):
        raise ToolError(
            f"Validation failed: Expected hash, found {type(dictobj).__name__!r}"
        )


def validate_keys(dictobj, keys, optional_keys=frozenset()):
    validate_dict(dictobj)
    for key in keys:
        if key not in dictobj:
            raise ToolError(f"Validation failed: missing {key!r}")
    for key in dictobj.keys():
        if key not in keys and key not in optional_keys:
            raise ToolError(f"Validation failed: superfluous key: {key!r}")


def validate_value_type(value, expected_type):
    if not isinstance(value, expected_type):
        raise ToolError(
            rf"Validation falied: Expected {expected_type.__name__}, got {value!r}"
        )


def validate_config(config):
    validate_keys(config, ("letsencrypt", "hosts"))
    validate_keys(config["letsencrypt"], ("email",), ("staging,"))
    validate_value_type(config["letsencrypt"].get("staging", False), bool)
    validate_dict(config["hosts"])
    for host, def_by_port in config["hosts"].items():
        validate_dict(def_by_port)
        for port, definitions in def_by_port.items():
            try:
                int(port)
            except (ValueError, TypeError):
                raise ToolError(
                    f"Validation failed: Expected port number as string, got {port!r}"
                )
            validate_value_type(definitions, list)
            for definition in definitions:
                validate_dict(definition)
                validate_keys(definition, ("location", "backend"), ("http_auth"))
                validate_value_type(definition["location"], str)
                if "http_auth" in definition:
                    validate_keys(
                        definition["http_auth"], ("realm", "username", "password")
                    )


def certbot_init(config):
    certbot_cmdline = ["certbot", "certonly", "--webroot", "-w", "/var/www/certbot", "--noninteractive", "--no-eff-email"]
    if config["letsencrypt"].get("staging"):
        certbot_cmdline.append("--staging")
    certbot_cmdline.extend(("--email", config["letsencrypt"]["email"]))
    for host in set(config["hosts"].keys()):
        certbot_cmdline.extend(("-d", host))
    certbot_cmdline.extend(("--rsa-key-size", "4096", "--agree-tos", "--force-renewal"))
    result = call(certbot_cmdline)
    if result != 0:
        raise ToolError("Unexpeced result from certbot", result)


quoting_re = re.compile('[{"\\\\\t\r\n]')
quote_table = {
    "\\": "\\\\",
    "\t": "\\t",
    "\n": "\\n",
    "\r": "\\r",
    "{": "\\{",
    '"': '\\"',
}


def nginx_quote_string(st):
    return '"' + quoting_re.sub(lambda mo: quote_table[mo.group(0)], st) + '"'


loc_strip_re = re.compile("[^a-zA-Z0-9_-]")


def make_htpasswd_filename(host, port, loc):
    loc_striped = loc_strip_re.sub("_", loc)
    fn = f"{host}.{port}.{loc_striped}"
    return os.path.join("/etc/nginx/htpasswd", fn)
    pass


def write_server_block(*, host, port, port_config, file):
    port_infix = f".{port}" if port != 443 else ""
    print(
        f"""
server {{
    listen {port} ssl;
    server_name {host};
    
    access_log /var/log/nginx/{host}{port_infix}.access.log;""",
        file=file,
    )
    for location in port_config:
        print(
            f"""
    location {location['location']} {{
      proxy_set_header        Host $host;
      proxy_set_header        X-Real-IP $remote_addr;
      proxy_set_header        X-Forwarded-For $proxy_add_x_forwarded_for;
      proxy_set_header        X-Forwarded-Proto $scheme;

      proxy_pass          {location['backend']};
      proxy_read_timeout  90;

      proxy_redirect http:// https://;
      proxy_http_version 1.1;

      proxy_set_header Upgrade $http_upgrade;
      proxy_set_header Connection $connection_upgrade;""",
            file=file,
        )
        if "http_auth" in location:
            htpasswd_filename = make_htpasswd_filename(host, port, location["location"])
            with open(htpasswd_filename, "w") as f:
                f.write(location["http_auth"]["username"])
                f.write(":")
                f.write(location["http_auth"]["password"])

            quoted_realm = nginx_quote_string(location["http_auth"]["realm"])
            print(f"      auth_basic {quoted_realm};", file=file)
            print(
                f"      auth_basic_user_file {nginx_quote_string(htpasswd_filename)};",
                file=file,
            )
        print("    }", file=file)
    print(f"""
    ssl_certificate /etc/letsencrypt/live/{host}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/{host}/privkey.pem;
    include /etc/nginx/certbot-ssl.conf;
    ssl_dhparam /etc/nginx/certbot-ssl-dhparams.pem;
}}""", file=file)


def update_nginx(config):
    for host, ports in config["hosts"].items():
        if not os.path.exists(
            os.path.join("/etc/letsencrypt/live", host, "fullchain.pem")
        ):
            # No certificate available. Nginx will fail if added
            continue
        for port, port_config in ports.items():
            port = int(port)
        with open('/etc/nginx/conf.d/letsexpose-hosts.conf',"w") as f:
            print("""map $http_upgrade $connection_upgrade {  
    default upgrade;
    ''      close;
}""", file=f)
            write_server_block(
                host=host, port=port, port_config=port_config, file=f
            )


def main():
    args = parse_args()
    try:
        config = load_config(args.config_file)
        validate_config(config)
        if args.task == "certbot-init":
            certbot_init(config)
        elif args.task == "update-nginx":
            update_nginx(config)
    except ToolError as e:
        print(f"{sys.argv[0]}: error: {e.message}")
        sys.exit(e.exit_code)
    except OSError as e:
        fns = ", ".join([repr(fn) for fn in (e.filename, e.filename2) if fn])
        if fns:
            fns = " " + fns
        print(f"{sys.argv[0]}: error: {e.strerror}" + fns)
        sys.exit(2)


if __name__ == "__main__":
    main()
