#!/usr/bin/env python3
# -*- coding:utf-8 -*-
import sys,os,time,subprocess
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

def log(s):
	print("Monitor %s"%s)

class MyFieldSystemEventHander(FileSystemEventHandler):
	def __init__(self,fn):
		super(MyFieldSystemEventHander,self).__init__()
		self.restart=fn
	def on_any_event(self,event):
		if event.src_path.endswith(".py"):
			log("python source file changed %s"%event.src_path)
			self.restart()
command=["echo","ok"]
process=None
def kill_process():
	global process
	if process:
		log("kill process[%s]"%process.pid)
		process.kill()
		process.wait()
		log("process ended with code %s"%process.returncode)
		process=None
def start_process():
	global process,command
	log("start process %s..."%" ".join(command))
	process=subprocess.Popen(command,stdin=sys.stdin,stdout=sys.stdout,stderr=sys.stderr)
def restart_process():
	kill_process()
	start_process()
def start_watch(path,callback):
	observer=Observer()
	observer.schedule(MyFieldSystemEventHander(restart_process),path,recursive=True) #如果path中有文件发生变动，restart。
	observer.start()
	log("watching directory %s"%path)
	start_process()
	try:
		while True:
			time.sleep(0.5)
	except KeyboardInterrupt:
		observer.stop()
	observer.join()

if __name__ == "__main__":
	argv=sys.argv[1:]
	if not argv:
		print("Usage:./pymonitor your-script.py")
		exit(0)
	if argv[0] != "python":
		argv.insert(0,"python")
	command=argv
	path=os.path.dirname(os.path.abspath(__file__))#此处为__file__非“__file__”
	print ("********",path)
	start_watch(path,None)