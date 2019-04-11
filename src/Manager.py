import sys
import docker
import logging
import socket
import os
import shutil
from contextlib import closing

from NginxConfigBuilder import *

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')

CONFIG_DIR = 'loadbalancer/'

LB = "loadbalancer"
SERVERS = "servers"
ADDR = "address"

IMAGE_APP = "hasnainmamdani/comp598_proj_testapp"
IMAGE_LB = "hasnainmamdani/comp598_proj_loadbalancer"

def find_a_free_port():
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(('localhost', 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


if __name__=="__main__":

    client = docker.from_env()
    active_apps = {}

    # localhost for now
    ip_addr = socket.gethostbyname(socket.gethostname())

    shutil.rmtree(CONFIG_DIR, ignore_errors=True)
    os.mkdir(CONFIG_DIR)

    while True:

        command = input("> ").split(' ')

        if command[0] == 'start':

            if len(command) != 2:
                logger.info("Incorrect format. Enter \"start <app_name>\"")
                continue

            app_name = command[1]

            if app_name in active_apps.keys():
                logger.info("App %s already running" % app_name)
                continue

            container_app = client.containers.run(IMAGE_APP, "python app.py", stderr=True, stdin_open=True, remove=True, detach=True)
            container_app_ip_addr = client.containers.get(container_app.id).attrs['NetworkSettings']['Networks']['bridge']['IPAddress']

            port = find_a_free_port()

            os.mkdir(CONFIG_DIR+app_name)

            create_nginx_config(port, app_name, container_app_ip_addr)
            container_lb = client.containers.run(IMAGE_LB, tty=True, stderr=True, stdin_open=True, ports={str(port)+'/tcp': port},
                                               name=app_name+"-loadbalancer", remove=True, detach=True,
                                               volumes={os.getcwd()+'/'+CONFIG_DIR+app_name: {'bind': '/etc/nginx', 'mode': 'ro'}})

            container_lb.exec_run('nginx -s reload')

            active_apps[app_name] = {}
            active_apps[app_name][ADDR] = ip_addr+":"+str(port)
            active_apps[app_name][LB] = container_lb
            active_apps[app_name][SERVERS] = [container_app]

            logger.info("Application %s started with one worker at %s:%d" % (app_name, ip_addr, port))

        elif command[0] == 'stop':
            if len(command) != 2:
                logger.info("Incorrect format. Enter \"stop <app_name>\"")
                continue

            app_name = command[1]

            if app_name not in active_apps.keys():
                logger.info("Application % is not active" % app_name)
                continue

            for server in active_apps[app_name][SERVERS]:
                server.stop(timeout=0)
            active_apps[app_name][LB].stop(timeout=0)
            del active_apps[app_name]

            shutil.rmtree(CONFIG_DIR+app_name)

            logger.info("Application %s stopped. All relevant containers destroyed" % (app_name))

        elif command[0] == 'scaleup':

            if len(command) != 3:
                logger.error("Incorrect format. Enter \"scaleup <app_name> <num_workers>\"")
                continue

            app_name = command[1]
            num_workers = int(command[2])

            if app_name not in active_apps.keys():
                logger.error("App % is not active" % app_name)
                continue

            if num_workers < 1:
                logger.error("Invalid number of worker to add = %d. It should be greater than zero. Skipping." %(num_workers))
                continue

            for i in range(num_workers):
                container_app = client.containers.run(IMAGE_APP, "python app.py", stderr=True, stdin_open=True, remove=True, detach=True)
                container_app_ip_addr = client.containers.get(container_app.id).attrs['NetworkSettings']['Networks']['bridge']['IPAddress']
                add_server(app_name, container_app_ip_addr)
                active_apps[app_name][SERVERS].append(container_app)

            container_lb = client.containers.get(app_name+"-loadbalancer")
            container_lb.exec_run('nginx -s reload')

            logger.info("Added %d more workers to the application %s. Total workers now = %d" % (num_workers, app_name, len(active_apps[app_name][SERVERS])))

        elif command[0] == 'scaledown':

            if len(command) != 3:
                logger.error("Incorrect format. Enter \"scaledown <app_name> <num_workers>\"")
                continue

            app_name = command[1]
            num_workers = int(command[2])

            if app_name not in active_apps.keys():
                logger.error("Application % is not active" % app_name)
                continue

            if num_workers < 1:
                logger.error("Invalid number of worker to remove = %d. It should be greater than zero. Skipping." %(num_workers))
                continue

            if len(active_apps[app_name][SERVERS]) <= num_workers:
                logger.error("User intended to remove all workers. Consider stopping the application with the 'stop' command.")
                continue

            for i in range(num_workers):
                container_app = active_apps[app_name][SERVERS][-1]
                container_app_ip_addr = client.containers.get(container_app.id).attrs['NetworkSettings']['Networks']['bridge']['IPAddress']
                remove_server(app_name, container_app_ip_addr)
                del active_apps[app_name][SERVERS][-1]

            container_lb = client.containers.get(app_name+"-loadbalancer")
            container_lb.exec_run('nginx -s reload')

            logger.info("Removed %d workers from the application %s. Total workers now = %d" % (num_workers, app_name, len(active_apps[app_name][SERVERS])))

        elif command[0] == 'ps':
            for app in active_apps.keys():
                logger.info("Application: %s, Address: %s, # workers: %d" % (app, active_apps[app][ADDR], len(active_apps[app][SERVERS])))

        elif command[0] == 'exit':
            # stop all before exiting
            sys.exit(0)

        else:
            logger.error("Invalid command")