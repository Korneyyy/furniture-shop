"""
Скрипт для настройки Nginx с SSL на сервере RUVDS
"""
import paramiko

HOST = "62.233.35.42"
USER = "root"
PASSWORD = "lr6q7zm3SK"
PORT = 22

NGINX_CONFIG = """server {
    listen 80;
    server_name biovostok.shop www.biovostok.shop;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name biovostok.shop www.biovostok.shop;

    ssl_certificate /etc/letsencrypt/live/biovostok.shop/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/biovostok.shop/privkey.pem;

    location /static/ {
        alias /var/www/biovostok/staticfiles/;
    }

    location /media/ {
        alias /var/www/biovostok/media/;
    }

    location / {
        include proxy_params;
        proxy_pass http://unix:/var/www/biovostok/biovostok.sock;
    }
}
"""

def run():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=15)

    # Write config via SFTP
    sftp = client.open_sftp()
    with sftp.open("/etc/nginx/sites-available/biovostok", "w") as f:
        f.write(NGINX_CONFIG)
    sftp.close()
    print("[OK] Nginx config written")

    # Verify file size
    stdin, stdout, stderr = client.exec_command("wc -c /etc/nginx/sites-available/biovostok")
    size = stdout.read().decode("utf-8", errors="replace").strip()
    print(f"[OK] File size: {size}")

    # Test nginx
    stdin, stdout, stderr = client.exec_command("nginx -t")
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    print(f"[NGINX TEST] {out} {err}")

    # Restart services
    stdin, stdout, stderr = client.exec_command(
        "systemctl restart nginx && systemctl restart biovostok && echo RESTARTED"
    )
    out = stdout.read().decode("utf-8", errors="replace")
    print(f"[RESTART] {out}")

    client.close()

if __name__ == "__main__":
    run()