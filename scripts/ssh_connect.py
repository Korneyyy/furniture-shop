"""
SSH-скрипт для подключения к серверу RUVDS и выполнения команд
"""

import paramiko
import sys

HOST = "62.233.35.42"
USER = "root"
PASSWORD = "lr6q7zm3SK"
PORT = 22

def run_command(command):
    """Подключается к серверу и выполняет команду"""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        print(f"Подключаюсь к {HOST}...", flush=True)
        client.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=15)
        print("Подключено!", flush=True)
        
        if command:
            stdin, stdout, stderr = client.exec_command(command)
            exit_status = stdout.channel.recv_exit_status()
            
            output = stdout.read().decode('utf-8', errors='replace')
            error = stderr.read().decode('utf-8', errors='replace')
            
            if output:
                sys.stdout.buffer.write(output.encode('utf-8', errors='replace'))
                sys.stdout.buffer.flush()
            if error:
                sys.stderr.write(error[:500] + '\n')
                sys.stderr.flush()
            
            if exit_status != 0:
                print(f"Команда завершилась с ошибкой (код {exit_status})", flush=True)
            
            return exit_status, output, error
        return 0, "", ""
    
    except Exception as e:
        print(f"Ошибка подключения: {e}", flush=True)
        return -1, "", str(e)
    finally:
        client.close()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        command = " ".join(sys.argv[1:])
    else:
        command = "echo 'connected' && cat /etc/os-release && uname -a && python3 --version"
    
    run_command(command)