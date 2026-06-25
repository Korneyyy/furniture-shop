"""
Скрипт для деплоя Django-проекта на сервер RUVDS
"""
import paramiko
import sys
import time
import os

HOST = "62.233.35.42"
USER = "root"
PASSWORD = "lr6q7zm3SK"
PORT = 22

os.environ['PYTHONIOENCODING'] = 'utf-8'

def log(msg):
    print(msg.encode('utf-8', errors='replace').decode('utf-8'))

def run_command(command, timeout=120):
    """Подключается к серверу и выполняет команду с таймаутом"""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        log(f"[CMD] {command[:80]}...")
        client.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=15)
        
        if command:
            stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
            exit_status = stdout.channel.recv_exit_status()
            
            output = stdout.read().decode('utf-8')
            error = stderr.read().decode('utf-8')
            
            if output:
                log(output)
            if error:
                log(f"[STDERR] {error[:200]}")
            
            return exit_status, output, error
        return 0, "", ""
    
    except Exception as e:
        log(f"[ERROR] {e}")
        return -1, "", str(e)
    finally:
        client.close()

def wait_for_apt():
    """Ждёт завершения всех apt процессов"""
    log("[WAIT] Ожидание завершения apt (проверка каждые 15 сек)...")
    for i in range(20):
        _, out, _ = run_command("ps aux | grep 'apt' | grep -v grep | wc -l")
        count = int(out.strip()) if out.strip() else 0
        if count == 0:
            log("[OK] apt завершён")
            return True
        log(f"  apt ещё работает (процессов: {count}), попытка {i+1}/20")
        time.sleep(15)
    return False

# === ЭТАП 1: Установка пакетов ===
def stage1_install_packages():
    log("\n=== ЭТАП 1: Установка пакетов ===")
    run_command("apt-get update -qq 2>&1 | tail -3")
    run_command("DEBIAN_FRONTEND=noninteractive apt-get install -y python3-venv python3-pip git nginx postgresql postgresql-client libpq-dev curl certbot python3-certbot-nginx build-essential python3-dev 2>&1 | tail -10")

# === ЭТАП 2: Настройка PostgreSQL ===
def stage2_setup_db():
    log("\n=== ЭТАП 2: Настройка PostgreSQL ===")
    run_command("""
        sudo -u postgres psql -c "CREATE USER biovostok_user WITH PASSWORD 'biovostok_pass123';" 2>/dev/null
        sudo -u postgres psql -c "CREATE DATABASE biovostok_db OWNER biovostok_user;" 2>/dev/null
        sudo -u postgres psql -c "ALTER USER biovostok_user CREATEDB;" 2>/dev/null
        sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE biovostok_db TO biovostok_user;" 2>/dev/null
        echo "PostgreSQL setup done"
    """)
    run_command("systemctl enable postgresql && systemctl restart postgresql && systemctl status postgresql --no-pager | head -5")

# === ЭТАП 3: Клонирование проекта ===
def stage3_clone_project():
    log("\n=== ЭТАП 3: Клонирование проекта ===")
    run_command("mkdir -p /var/www && rm -rf /var/www/biovostok")
    run_command("git clone https://github.com/Korneyyy/furniture-shop.git /var/www/biovostok")

# === ЭТАП 4: Виртуальное окружение ===
def stage4_setup_venv():
    log("\n=== ЭТАП 4: Настройка виртуального окружения ===")
    run_command("cd /var/www/biovostok && python3 -m venv venv && source venv/bin/activate && pip install --upgrade pip && pip install -r requirements.txt gunicorn psycopg2-binary 2>&1 | tail -10")

# === ЭТАП 5: Создание .env ===
def stage5_create_env():
    log("\n=== ЭТАП 5: Создание .env ===")
    env_content = 'SECRET_KEY=django-insecure-prod-key-change-me-in-production\nDEBUG=False\nALLOWED_HOSTS=biovostok.com,www.biovostok.com,62.233.35.42\nDATABASE_URL=postgres://biovostok_user:biovostok_pass123@localhost:5432/biovostok_db\nCLOUDINARY_CLOUD_NAME=\nCLOUDINARY_API_KEY=\nCLOUDINARY_API_SECRET=\nTELEGRAM_BOT_TOKEN=\nTELEGRAM_CHAT_ID=\n'
    run_command(f"cat > /var/www/biovostok/.env << 'EOF'\n{env_content}EOF\n")
    run_command("cat /var/www/biovostok/.env")

# === ЭТАП 6: Миграции и статика ===
def stage6_migrate():
    log("\n=== ЭТАП 6: Миграции и статика ===")
    run_command("cd /var/www/biovostok && source venv/bin/activate && python manage.py migrate --noinput 2>&1 | tail -15")
    run_command("cd /var/www/biovostok && source venv/bin/activate && python manage.py collectstatic --noinput 2>&1 | tail -5")
    run_command("cd /var/www/biovostok && source venv/bin/activate && python -c \"from django.contrib.auth import get_user_model; User = get_user_model(); User.objects.filter(username='admin').exists() or User.objects.create_superuser('admin', 'admin@example.com', 'admin123')\" 2>&1")

# === ЭТАП 7: Gunicorn service ===
def stage7_setup_gunicorn():
    log("\n=== ЭТАП 7: Настройка Gunicorn ===")
    gunicorn_service = ('[Unit]\nDescription=BioVostok Django App\nAfter=network.target\n\n'
        '[Service]\nUser=root\nGroup=root\nWorkingDirectory=/var/www/biovostok\n'
        'ExecStart=/var/www/biovostok/venv/bin/gunicorn --workers 3 --bind unix:/var/www/biovostok/biovostok.sock config.wsgi:application\n'
        'Restart=always\n\n[Install]\nWantedBy=multi-user.target\n')
    run_command(f"cat > /etc/systemd/system/biovostok.service << 'EOF'\n{gunicorn_service}EOF\n")
    run_command("systemctl daemon-reload && systemctl start biovostok && systemctl enable biovostok && systemctl status biovostok --no-pager | head -10")

# === ЭТАП 8: Nginx ===
def stage8_setup_nginx():
    log("\n=== ЭТАП 8: Настройка Nginx ===")
    nginx_conf = ('server {\n    listen 80;\n    server_name biovostok.com www.biovostok.com 62.233.35.42;\n\n'
        '    location /static/ {\n        alias /var/www/biovostok/staticfiles/;\n    }\n\n'
        '    location /media/ {\n        alias /var/www/biovostok/media/;\n    }\n\n'
        '    location / {\n        include proxy_params;\n        proxy_pass http://unix:/var/www/biovostok/biovostok.sock;\n    }\n}\n')
    run_command(f"cat > /etc/nginx/sites-available/biovostok << 'EOF'\n{nginx_conf}EOF\n")
    run_command("ln -sf /etc/nginx/sites-available/biovostok /etc/nginx/sites-enabled/ && rm -f /etc/nginx/sites-enabled/default && nginx -t && systemctl restart nginx && systemctl status nginx --no-pager | head -5")

# === ЭТАП 9: SSL ===
def stage9_setup_ssl():
    log("\n=== ЭТАП 9: SSL (опционально) ===")
    result = run_command("certbot --nginx -d biovostok.com -d www.biovostok.com --non-interactive --agree-tos -m admin@biovostok.com 2>&1 | tail -5")
    if result[0] != 0:
        log("SSL не настроен (возможно домен не указывает на сервер). Пропускаем.")

# === ЭТАП 10: Финальная проверка ===
def stage10_final_check():
    log("\n=== ЭТАП 10: Финальная проверка ===")
    run_command("""
        echo "=== Проверка сервисов ==="
        echo "PostgreSQL: $(systemctl is-active postgresql)"
        echo "Nginx: $(systemctl is-active nginx)"
        echo "Gunicorn: $(systemctl is-active biovostok)"
        echo ""
        echo "=== Статика ==="
        ls -la /var/www/biovostok/staticfiles/ 2>&1 | head -5
        echo ""
        echo "=== HTTP тест ==="
        curl -s -o /dev/null -w "HTTP Status: %{http_code}\n" http://localhost/
    """)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        stage = sys.argv[1]
        stages = {
            "1": stage1_install_packages,
            "2": stage2_setup_db,
            "3": stage3_clone_project,
            "4": stage4_setup_venv,
            "5": stage5_create_env,
            "6": stage6_migrate,
            "7": stage7_setup_gunicorn,
            "8": stage8_setup_nginx,
            "9": stage9_setup_ssl,
            "10": stage10_final_check,
        }
        if stage in stages:
            stages[stage]()
        else:
            print("Укажите этап от 1 до 10")
    else:
        log("Запуск всех этапов деплоя...")
        run_command("kill -9 $(pgrep -f 'apt install') 2>/dev/null; sleep 3")
        wait_for_apt()
        
        stage1_install_packages()
        wait_for_apt()
        stage2_setup_db()
        stage3_clone_project()
        stage4_setup_venv()
        stage5_create_env()
        stage6_migrate()
        stage7_setup_gunicorn()
        stage8_setup_nginx()
        stage9_setup_ssl()
        stage10_final_check()
        log("Деплой завершён!")