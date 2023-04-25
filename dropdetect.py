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
from datetime import datetime as dt
import time,threading,sys,os,socket
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
		thread_list=[]

		print(f"[|X:{MY_NAME}]: Running as server...")
		#Do handshake
		try:
			serv,cli,info_dict=server.doHandshake(PARSER["ip"],PARSER["port"])
			print(f"[|X:{MY_NAME}]: info_dict: {info_dict}")
		except PermissionError:
			return 1
		#Start main loop
		# print(f"[|X:{MY_NAME}]: Starting main loop...")
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

		#Spawn the heartbeat server
		print(f"[|X:{MY_NAME}]: Starting heartbeat on data socket...")
		hb_thread=threading.Thread(target=server.heartbeat,
							args=(serv,
										cli,
										b'___heart_beat___',
										1),
							daemon=True)
		hb_thread.start()

		#Join threads
		for t in thread_list:
			t.join()
		print(f"[|X:{MY_NAME}]: Done!")
		#Kill heartbeat (or at least close socket)
		serv.close()

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
		screen.write((stat_thread_count:=ceil(total/PARSER["chunk"])))

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
			screen.notify("Couldn't connect to server (doesn't seem ready)!",colour='\033[41m')
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
		except socket.timeout:
			screen.notify(f"Couldn't connect to server (data port seems blocked)!",colour='\033[41m')
			screen.getLeave()
			return 1
		if cli==None:
			screen.notify(f"Couldn't complete handshake!",colour='\033[41m')
			return 1
		#Start thread-spawning loop
		main_id=b'______main______'
		full_list={"close":[],"drop":[],"srverr":[]}  #List of dropped/closed ports
		sums={"accept":0,"close":0,"drop":0,"srverr":0}
		thread_list=[]
		main_start_time=int(time.time())

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

		#Start heartbeat from cli
		# screen.notify("Starting heartbeat...")
		hb_thread=threading.Thread(target=client.heartbeat,
							args=(cli,1),
							daemon=True)
		hb_thread.start()

		#Wait for all threads...
		weight=total/PARSER["chunk"]
		done_threads=0
		for t in thread_list:
			t.join()

		main_end_time=int(time.time())

		#Print results
		if globe.hb_event.is_set():
			screen.notify("Heartbeat died!",colour='\033[41m')
			screen.nnotify("Results will be unreliable:",colour='\033[41m')
		else:
			screen.notify("Results:")
		thresh=total//4  #Highest a sum can be (inclusive)

		#Print a special acceptance message if any of the sums are equal to the total
		if sums["accept"]==total:
			globe.all_lists["accept"].sort()
			screen.nnotify("All ports open!",colour='\033[42m')
		else:
			for r in sums.items():  #sums is a dict; Ex: {"accept":20}; 20 accepted packets
				globe.all_lists[r[0]].sort()  #Sort all lists because we might save them later
				if 0<r[1]<=thresh:
					screen.nnotify(f"{r[0]}: {globe.all_lists[r[0]]}")
		#Save results if option is set
		if PARSER["outfile"]:
			with open(PARSER["outfile"],'w') as f:
				cur_date=dt.now().strftime(f"%Y.%m.%d:")
				prev_time=dt.fromtimestamp(main_start_time).strftime(f"%H:%M:%S")
				cur_time=dt.fromtimestamp(main_end_time).strftime(f"%H:%M:%S")
				f.write(f"""       ___________________
__--++* DropDetect Report *++--__
|-------------------------------|
|  {cur_date}                  |
|    {f'''{prev_time} - {cur_time}''':<27}|
|    {f'''{main_end_time-main_start_time}s elapsed''':<27}|
|-------------------------------|
|  Server:     {PARSER["ip"]:<17}|
|  Data Port:  {PARSER["port"]:<17}|
|  Port Range: {f'''{PARSER["start"]}-{PARSER["end"]}''':<17}|
|  Total:      {f'''{total} ports''':<17}|
|                               |
|  Chunk Size: {f'''{PARSER["chunk"]}/thread''':<17}|
|  Threads:    {stat_thread_count:<17}|
|  Fail Delay: {f'''{PARSER["delay"]}s''':<17}|
=================================
|\n""")
				for r in globe.all_lists.items():
					if not r[1]:  #Ignore empty lists
						f.write(f"|  {r[0]}: Empty\n")
						continue
					elif len(r[1])==1:  #Write just the one item, otherwise it'll get ignored
						f.write(f"|  {r[0]}: {r[1][0]}\n")
						continue

					ranges_list=[]
					range_bottom=r[1][0]
					range_top=range_bottom
					# screen.nnotify(f"""{r[0]}: {r[1]}""")
					#Convert consecutive ports to a range
					r[1].append(-1)  #Append a negative so the loop doesn't ignore the last legitimate port
					for p in r[1][1:]:
						if p==range_top+1:  #Just increment the range top
							range_top+=1
						elif range_top==range_bottom:  #Only one port in the range
							ranges_list.append(f"{range_top}")
							range_bottom,range_top=p,p
						else:  #Save the current range as a string
							ranges_list.append(f"{range_bottom}-{range_top}")
							range_bottom,range_top=p,p

					f.write(f"|  {r[0]}: {', '.join([i for i in ranges_list])}\n")
				f.write("|\n=================================")
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
		if not PARSER["server"]:
			screen.exitGrid()
		print('\r\033[K',end='')
