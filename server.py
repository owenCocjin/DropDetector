## Author:  Owen Cocjin
## Version: 0.1
## Date:    2021.12.23
## Description:    Holds server functions
import socket,multiprocessing,time,os
import data,globe
from misc import iToB,bToI

MY_NAME=__file__[__file__.rfind('/')+1:-3]
ports_manager=data.Ports(1,1025,100)
threads_manager={}

def doHandshake(data_addr="0.0.0.0",data_port=8080):
	'''Starts a data server'''
	#Default values
	info_dict={"main_id":None,  #Can't be None!
	"timeout":3,
	"port_start":1,
	"port_end":1025,
	"port_chunk":100}
	#Create socket
	serv=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
	serv.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
	serv.bind((data_addr,data_port))
	serv.listen()
	print(f"[|X:{MY_NAME}:doHandshake]: Started server")
	#Accept connection
	cli,cli_addr=serv.accept()
	print(f"[|X:{MY_NAME}:doHandshake]: Got connection from {cli_addr}!")
	#Receive start of handshake
	recv=data.recvUnit(cli)
	if recv.content!=0:
		print(f"[|X:{MY_NAME}:doHandshake]: Didn't receive handshake! Closing...")
		cli.close()
		serv.close()
		return None
	#Save the ID
	info_dict["main_id"]=recv.key
	print(f"[|X:{MY_NAME}:doHandshake]: Main ID: {info_dict['main_id']}")
	#Send OK
	ok_unit=data.Unit(b'\x08'+info_dict["main_id"])
	cli.send(ok_unit.raw)
	#Receive info
	while True:
		recv=data.recvUnit(cli)
		if recv.payload[0]==0xff:
			print(f"[|X:{MY_NAME}:doHandshake]: Finished setup")
			break
		try:
			#print(recv)
			toadd=data.handshake_payload_types[recv.payload[0]]
			info_dict[toadd[0]]=toadd[1](recv.payload[1:])
		except KeyError:
			print(f"[|X:{MY_NAME}:doHandshake]: Client send a non-existent payload type: {hex(recv.payload[0])}")
			unit=data.Unit(b'\x44'+info_dict["main_id"])
			unit.setPayload(b"BAD_HANDSHAKE_PAYLOAD:"+recv.payload[0:1])
			cli.send(unit.raw)
			cli.close()
			serv.close()
			return None
	#Check for well-known ports, and see if we have enough permissions
	if info_dict["port_start"]<1024 and os.getuid():  #UID is anything but 0
		print(f"[|X:{MY_NAME}:doHandshake]: Not enough permissions to start!")
		ok_unit=data.Unit(b'\x44'+info_dict["main_id"])
		ok_unit.setPayload(b'NOT_ENOUGH_PERMISSION')
		cli.send(ok_unit.raw)
		raise PermissionError
	#Send OK
	cli.send(ok_unit.raw)
	print(f"[|X:{MY_NAME}:doHandshake]: Finished handshake!")
	return (serv,cli,info_dict)

def tryPort(addr,port,timeout):
	'''Tries to receive data on port
	Returns an int:
		0=Ok
		1=Bad'''
	#Create socket
	server=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
	server.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
	server.settimeout(timeout)
	server.bind((addr,port))
	server.listen()
	try:
		print(f"[|X:{MY_NAME}:tryPort]: Trying port {port}...")
		client,cli_addr=server.accept()
		#print(f"[|X:{MY_NAME}:tryPort]: Got connection from {cli_addr}")
	except socket.timeout:
		print(f"[|X:{MY_NAME}:tryPort]: ({port}) Timedout")
		return 2
	#Get OK
	unit=data.Unit(data.recvFrom(client,17))  #Only expecting 17 bytes
	#print(f"|X:{MY_NAME}:tryPort]: Unit: {unit}")
	if not unit.status:
		#print(f"[|X:{MY_NAME}:tryPort]: Bad request!")
		return 1
	#print(f"[|X:{MY_NAME}:tryPort]: Got OK!")
	#Reply with OK
	unit.setWhoByte(0b01001000)
	unit.compile()
	client.send(unit.raw)
	# print(f"[|X:{MY_NAME}:tryPort]: Sent OK")
	client.close()
	server.close()

def minion_thread(data_addr,ports,timeout):
	'''Main thread for threads spawned by thread_manager_main'''
	#Convert ports to int list
	port_list=[bToI(ports[i:i+2]) for i in range(0,len(ports),2)]
	#Loop through all ports
	timeout_ext=1
	for p in port_list:
		#print(f"[|X:{MY_NAME}:minion_thread]: Trying port {p}...")
		try:
			tryPort(data_addr,p,timeout*timeout_ext)
		except OSError as e:
			if e.errno==98:  #Port in use
				print(f"[|X:{MY_NAME}:tryPort]: Port {p} already in use! Extending timeout for next port")
				timeout_ext+=1
				continue
		timeout_ext=1
	return True

def heartbeat(serv,cli,heartbeat_id,bps=3):
	'''Main thread to start a heartbeat and allow sending messages to/from server'''
	#Set client timeout to bps+1 (+1 as a buffer)
	cli.settimeout(bps+1)
	#Set global OK message
	globe.serv_err_unit=data.Unit(b'\x4c'+heartbeat_id)
	globe.serv_err_unit.setPayload(b'OK')
	#Start loop
	while True:
		#Receive from client
		recv=data.recvUnit(cli)
		if not recv:
			print(f"[|X:{MY_NAME}:heartbeat]: Client died")
			return 1
		if recv.content!=4:
			print(f"[|X:{MY_NAME}:heartbeat]: Bad heartbeat from client")
			#Reply with close
			reply=data.Unit(b'\x44'+heartbeat_id)
			reply.setPayload(b"INCORRECT_HEARTBEAT")
			cli.send()
			serv.close()
			return 1
		elif not recv.status:
			print(f"[|X:{MY_NAME}:heartbeat]: Client sent error: {recv.payload.decode()}")
			return 2
		else:
			print(f"|X> {recv.payload.decode()}")
		#Send OK or error
		cli.send(globe.serv_err_unit.raw)
		#Close thread if error is bad
		if not globe.serv_err_unit.status:
			return 2

if __name__=="__main__":
	addr="0.0.0.0"
	port=8080
	serv=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
	serv.bind((addr,port))
	serv.listen()
	cli,cli_addr=serv.accept()

	print("Starting heartbeat")
	heartbeat(serv,cli,b'___heart_beat___')
