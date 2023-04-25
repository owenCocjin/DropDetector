## Author:  Owen Cocjin
## Version: 0.1
## Date:    2021.12.23
## Description:    Holds client functions
## Notes:
##  - info_dict in the handshake must be {'b\xNN':b'\xVALUE'}
##    where \xNN is according to data.handshake_payload_types
import socket,time,multiprocessing,random,os
import data,grid,globe
from misc import iToB,bToI

MY_NAME=__file__[__file__.rfind('/')+1:-3]

def doHandshake(serv_addr,data_port,info_dict,id=b'______main______'):
	'''Complete handshake with server on defined data port'''
	cli=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
	cli.settimeout(bToI(info_dict[b'\x00']))  #This should be the only one needed to be converted back to int
	cli.connect((serv_addr,data_port))
	# print(f"[|X:{MY_NAME}:doHandshake]: Starting handshake...")
	unit=data.Unit(b'\x88'+id)
	#Send unit
	cli.send(unit.raw)
	#Get OK reply
	reply=data.recvUnit(cli)
	if not reply.status or reply.content!=0:
		# print(f"[|X:{MY_NAME}:doHandshake]: Bad reply from server!")
		return None
	#Send all important data
	# print(f"[|X:{MY_NAME}:doHandshake]: Sending setup data...")

	unit=data.Unit(b'\x8c'+id)
	for d in info_dict.items():
		unit.setPayload(d[0]+d[1])
		cli.send(unit.raw)
	#Send finished message
	unit.setPayload(b'\xff')
	cli.send(unit.raw)
	#Get OK from server
	recv=data.recvUnit(cli)
	if not recv.status:
		message=recv.getMessage()
		if not message:
			return None
		raise data.HandshakeError(*message)
		# finally:
		# 	return None
	# print(f"[|X:{MY_NAME}:doHandshake]: Finished handshake!")
	return cli

def tryPort(id,addr,port,timeout,delay):
	'''Tries conencting to a port.
	Returns an int:
		0=ACCEPTED
		1=CLOSED
		2=DROPPED
		3=SERVER ERROR (Bad reply)
	'''
	# print(f"[|X:{MY_NAME}:tryPort]: Trying port {port}...")
	counter=3
	while counter>0:
		try:
			#Create socket
			client=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
			client.settimeout(timeout)
			client.connect((addr,port))
			# print(f"[|X:{MY_NAME}:tryPort]: Connected!")
			break
		except socket.timeout:
			# print(f"[|X:{MY_NAME}:tryPort]: Timeout!")
			return 2
		except (ConnectionRefusedError,ConnectionResetError):
			# print(f"[|X:{MY_NAME}:tryPort]:({port}) Closed!")
			time.sleep(delay)
		except ConnectionAbortedError:  #Generic error, isn't an issue
			continue  #Skip counter decrement
		counter-=1
	if counter==0:  #Not timeout, but couldn't connect
		# print(f"[|X:{MY_NAME}:tryPort]: Couldn't establish connection!")
		return 1
	#Send OK
	unit=data.Unit(b'\xc8'+id)
	client.send(unit.raw)
	#Get OK
	try:
		recv_data=data.recvFrom(client,17)
		if recv_data==b'':  #Socket closed by server, but we are still open. We will assume this as "SRVERR" (as this is normally "port in use")
			return 3
		unit=data.Unit(recv_data)  #Only expecting 17 bytes
	except ConnectionResetError:  #Socket closed unexpectedly
		return 3
	if unit.status and unit.key==id:
		# print(f"[|X:{MY_NAME}:tryPort]: {id}: Got OK on port {port}")
		return 0
	else:
		# print(f"[|X:{MY_NAME}:tryPort]: {id}: Got BAD on port {port}")
		return 3  #Technically, this did go through
	#Close socket
	client.close()

def minion_thread(data_addr,ports,timeout,delay,screen,sums):
	'''Main thread for threads spawned from thread_manager_main'''
	#Generate ID
	my_id=b''
	for i in range(16):
		my_id+=iToB(random.randint(0,255))
	unit=data.Unit(b'\x58'+my_id)

	my_sums={"accept":0,"close":0,"drop":0,"srverr":0}  #Dict to update grid
	# toret={"close":[],"drop":[],"srverr":[]}
	for p in ports:
		# print(f"[|X:{MY_NAME}:minion_thread]: Trying port {p}...")
		#Make sure the globe.hb_event isn't set, or else we need to die
		if globe.hb_event.is_set():
			# print(f"[|X:{MY_NAME}:tryPort]: Heartbeat died and so shall I!")
			screen.notify("Heartbeat died and so shall I!",colour='\033[41m')
			return False

		res=tryPort(my_id,data_addr,p,timeout,delay)
		if res==0:  #Accepted
			my_sums["accept"]+=1
			globe.all_lists["accept"].append(p)
		elif res==1:  #Closed
			my_sums["close"]+=1
			globe.all_lists["close"].append(p)
		elif res==2:  #Dropped/Anything else
			my_sums["drop"]+=1
			globe.all_lists["drop"].append(p)
		else:
			my_sums["srverr"]+=1
			globe.all_lists["srverr"].append(p)
		# print()
	#Printing results
	globe.LOCK.acquire()
	screen.goTo(0,1)
	for s in sums:
		sums[s]+=my_sums[s]
		screen.write(sums[s])
	screen.goTo(1,4)
	globe.thread_count-=1
	screen.write(globe.thread_count)
	globe.LOCK.release()
	# return toret

def heartbeat(cli,bps=3):
	'''Main thread to start a heartbeat and allow sending messages to/from server'''
	#Set timeout to bps
	cli.settimeout(bps+1)  #+1 for buffer
	#Setup OK message
	heartbeat_id=b'___heart_beat___'
	globe.cli_err_unit=data.Unit(b'\xcc'+heartbeat_id)
	globe.cli_err_unit.setPayload(b'OK')
	#Start loop
	while True:
		try:
			#Send OK to server
			cli.send(globe.cli_err_unit.raw)
			#Receive OK
			reply=data.recvUnit(cli)
			if not reply:
				# print(f"[|X:{MY_NAME}:heartbeat]: Server died")
				return 1
			if reply.status:
				# print(f"<X| {reply.payload.decode()}")
				#Sleep the bps
				time.sleep(bps)
				continue
			#Error
			# print(f"[|X:{MY_NAME}:heartbeat]: Server sent error: {reply.payload.decode()}")
			return 2
		except Exception as e:
			# print(f"[|X:{MY_NAME}:heartbeat]: {e.__class__.__name__}: {e}")
			globe.hb_event.set()
			return 3

if __name__=="__main__":
	addr="0.0.0.0"
	port=8080
	# id=b'___heart_beat___'

	cli=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
	cli.connect((addr,port))

	heartbeat(cli)
