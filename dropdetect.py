#!/usr/bin/python3
## Author:  Owen Cocjin
## Version: 0.3
## Date:    2022.02.27
## Description:    Tests for network interference
## Updates:
##  - Fixed error output when hanshake fails to timeout
##  - Implemented outputting to file
from progmenu import MENU
from misc import iToB,bToI
from math import ceil
import time,threading,sys,os
import grid,server,client,data,globe
import menuentries

try:
	PARSER=MENU.parse(True)
except KeyboardInterrupt:
	print('\r\033[K',end='')
	exit(1)

MY_NAME=__file__[__file__.rfind('/')+1:-3]
S=7
screen=grid.Grid(4,5,grid.Unit(S),draw=False)

def main():
	#Determine if client or server
	if PARSER["server"]:
		print(f"[|X:{MY_NAME}]: Running as server...")
		#Do handshake
		try:
			serv,cli,info_dict=server.doHandshake(PARSER["ip"],PARSER["port"])
		except PermissionError:
			return 1
		#Start main loop
		# print(f"[|X:{MY_NAME}]: Starting main loop...")
		thread_list=[]
		for p in data.Ports(info_dict["port_start"],info_dict["port_end"],info_dict["port_chunk"]):
			#Wait for client port request
			recv=data.recvUnit(cli)
			if not recv.status or recv.content!=2:
				print(f"[|X:{MY_NAME}]: Non/bad port request from client")
				unit=data.Unit(b'\xc4'+info_dict["main_id"])
				unit.setPayload(b"BAD_PORT_REQUEST")
				#Close
				cli.close()
				serv.close()
				return None
			#Send next ports
			print(f"[|X:{MY_NAME}]: Sending: {p}")
			unit=data.Unit(b'\xbc'+info_dict["main_id"])
			unit.setPayload(iToB(len(p)//2,2)+p)
			cli.send(unit.raw)
			#Spawn threads
			thread_list.append(threading.Thread(target=server.minion_thread,
			args=(PARSER["ip"],
				p,
				info_dict["timeout"])))
			thread_list[-1].start()
		#Join threads
		for t in thread_list:
			t.join()
		print(f"[|X:{MY_NAME}]: Done!")
	else:
		total=PARSER["end"]-PARSER["start"]
		#Draw grid
		screen.enterGrid()
		screen.goTo()
		screen.drawUnit(grid.Unit(S,'\033[42m',"ACPT"))
		screen.drawUnit(grid.Unit(S,'\033[43m',"CLOSE"))
		screen.drawUnit(grid.Unit(S,'\033[41m',"DROP"))
		screen.drawUnit(grid.Unit(S,'\033[45m',"SRVERR"))
		screen.moveLinear(8)
		screen.drawUnit(grid.Unit(S,'\033[44m',"Total:"))
		screen.write(total)
		screen.write(f"(~{PARSER['chunk']}")
		screen.write("/chunk)",True)
		screen.moveLinear(1)
		screen.drawUnit(grid.Unit(S,'\033[44m',"Procs:"))
		screen.write("0")
		screen.write("of")
		screen.write(ceil(total/PARSER["chunk"]))

		#This doesn't actually help that much!
		#I'll have to get the server to check it's permissions instead
		#Check for permissions if we're testing well-known ports
		# if (1<=PARSER["start"]<=1024 or 1<=PARSER["end"]<=1024)\
		# 	and\
		# 	os.getuid()!=0:
		# 	screen.notify(f"Can't start:",colour="\033[41m")
		# 	screen.nnotify(f"  Not enough permissions for port range {PARSER['start']}-{PARSER['end']}",colour="\033[41m")
		# 	screen.getLeave()
		# 	return 1

		#Assemble args into a dict.
		#Each key+value must be a byte
		info_dict={}  #Any defaults are set by menuentries
		for a in data.handshake_payload_client.items():
			#Look up the arg in data.handshake_payload_client and try converting the data
			try:
				info_dict[a[1][0]]=a[1][1](PARSER[a[0]])
			except KeyError:
				continue
		#Do handshake
		try:
			screen.notify("Starting handshake...")
			cli=client.doHandshake(PARSER["ip"],
			PARSER["port"],
			info_dict)
		except ConnectionRefusedError:
			screen.notify("Couldn't connect to server!",colour='\033[41m')
			screen.getLeave()
			return 1
		except data.HandshakeError as e:
			screen.notify("Server sent an error:",colour='\033[41m')
			screen.nnotify(f"  [{e.message}]",colour='\033[41m')
			screen.getLeave()
			return 2
		except TimeoutError:
			screen.notify(f"Server timedout on port {PARSER['port']}!",colour='\033[41m')
			screen.getLeave()
			return 3
		if cli==None:
			screen.notify(f"Couldn't complete handshake!",colour='\033[41m')
			return 1
		#Start thread-spawning loop
		main_id=b'______main______'
		full_list={"close":[],"drop":[],"srverr":[]}  #List of dropped/closed ports
		sums={"accept":0,"close":0,"drop":0,"srverr":0}
		thread_list=[]
		screen.notify("Starting main loop")
		while True:
			#Make port request
			unit=data.Unit(b'\x28'+main_id)
			cli.send(unit.raw)
			#Get port reply
			recv=data.recvUnit(cli)
			if not recv.status or recv.content!=3:
				screen.notify(f"Bad port response from server!",colour='\033[41m')
				if recv.content==4 and recv.hasPayload:
					screen.nnotify(recv.payload.decode())
				cli.close()
				return None
			elif recv.payload[0:2]==b'\x00\x00':
				break
			#Extract ports from server message
			port_list=[]
			for p in range(0,bToI(recv.payload[0:2])*2,2):
				port_list.append(bToI(recv.payload[p+2:p+4]))
			#Spawn thread to connect to ports
			thread_list.append(threading.Thread(target=client.minion_thread,
				args=(PARSER["ip"],
					port_list,
					bToI(info_dict[b'\x00']),
					PARSER["delay"],
					screen,
					sums)))
			thread_list[-1].start()
			globe.LOCK.acquire()
			globe.thread_count+=1
			screen.goTo(1,4)
			screen.write(globe.thread_count)
			globe.LOCK.release()
			# screen.nnotify(f"Started thread #{len(thread_list)} ({port_list[0]}-{port_list[-1]})")
		screen.notify("Done asking for ports!")
		#Wait for all threads...
		weight=total/PARSER["chunk"]
		done_threads=0
		for t in thread_list:
			t.join()

		#Print results
		screen.notify("Results:")
		thresh=total//4  #Highest a sum can be (inclusive)
		for r in sums.items():  #sums is a dict; Ex: {"accept":20}; 20 accepted packets
			globe.all_lists[r[0]].sort()  #Sort all lists because we might save them later
			if 0<r[1]<=thresh:
				screen.nnotify(f"{r[0]}: {globe.all_lists[r[0]]}")
		#Save results if option is set
		if PARSER["outfile"]:
			with open(PARSER["outfile"],'w') as f:
				f.write(f"""__--++* DropDetect Report *++--__\n
Port range: {PARSER["start"]} - {PARSER["end"]}\n\n""")
				for r in globe.all_lists.items():
					# screen.nnotify(f"""{r[0]}: {r[1]}""")
					f.write(f"{r[0]}: {', '.join([str(i) for i in r[1]])}\n")
			screen.nnotify(f"Saved output to {PARSER['outfile']}!")

		screen.nnotify("Done! Press [Enter] to finish",colour='\033[42m')
		input()
		screen.exitGrid()

def err(text,flush=True):
	'''Prints to stderr'''
	sys.stderr.write(text)
	if flush:
		sys.stderr.flush()

if __name__=="__main__":
	try:
		main()
	except KeyboardInterrupt:
		screen.exitGrid()
		print('\r\033[K',end='')
