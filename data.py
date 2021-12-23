## Author:  Owen Cocjin
## Version: 0.1
## Date:    2021.12.23
## Description:    Holds anything related to data, or the management thereof
## Notes:
##  - Unit.buildUnit will auto-XOR secret key if who is a server!
##  - Data unit format:
'''
   0  |  1  |  2  |  3  |  4  |  5  |  6  |  7
| Who |         Secret Key (16 bytes)            |
|                                                |
|     | Payload .....
* Who is a bitmap:
  [1 byte] 0bWCCCSPUU
  0:   #Who is the message from?
    0: Server
    1: Client
  1-3:   #What are the contents of this message?
    0: Handshake
    1: Port request
    2: Port response
    4: Informational message
    5: Generic media message
  4:  #Message status, normally only for replies
    0: Status BAD
    1: Status OK
  5:  #Is there a payload in this message?
    0: No
    1: Yes
  6-7:
    Unused
* Secret key is used to confirm users, or validate initial handshake
  [16 bytes]
* Payload is the message payload.
  This should only exist if the 5th bit is 1 in the who_byte
  [n bytes]

__--++* Payload Format *++--__
  - All payloads start with 2 bytes describing the payload length, excluding those 2 bytes
  - A "handshake" payload follows:
    [bytes (inclusive)]
    [0-1]: Length of payload (excluding these bytes)
    [2]: Number describing the data in the payload
    [3-n]: Payload data (No requirement to exist)
  - A "port request" has no payload.
  - A "port reply" payload follows:
    [bytes (inclusive)]
    [0-1]: Message length (excluding these 2 bytes)
    [2-3]: Number of ports in this message
    [4-n]: Ports, each 2 bytes in length
  - An "informational message" payload follows:
    [bytes (inclusive)]
    [0-1]: Message length (excluding these 2 bytes)
    [2-n]: Text message describing information
  - A "generic media message" has no payload.
__--++* Handshake Format *++--__
  - Client reaches out to server with content=0 (handshake) and who=1 (client)
  - Server replies with content=0, status=1, and who=0.
  - The client sends any data required to setup connection (timeout, etc...).
    Note: Data sent by the client is always interpreted as raw data.
    Ex: If the timeout is to be 6 seconds, the client will send raw data: b'\x8c...KEY...\x02\x00\x06'
  - Once the client sends a handshake type of 0xff, the server will acknowledge by sending a payload-less reply.
    The handshake is complete at this stage
  - Handshake data values (byte 2 of payload):
    - 00: timeout
	- ff: handshake done
__--++* Port Reply Format *++--__
  - Client sends port request
  - If the server has any ports to return, send a standard port reply
  - If the server has exausted all ports, reply with an empty port reply (bytes 2-3=\x00\x00 w/ no ports list)
    No further communication will be done from here and both sides should close the data connection

__--++* Heartbeat *++--__
  - The heartbeat is a thread that will allow both server and client to ensure either exists.
  - The heartbeat will also be the main way to send messages between server/client.
  - Heartbeat follows this order:
    1. Server starts listening for heartbeat w/o timer
    2. Client starts heartbeat, sending a generic OK every N seconds (default 3)
    3. Server replies to the heartbeat with a generic OK
  - Both parties are allowed to send informational messages during the heartbeat, which should be interpreted as required.
  - If one party doesn't reply, assume they have died, and finish our own processes
'''
import socket
import payload
from misc import iToB, bToI

class Unit():
	def __init__(self,raw=None):
		if raw==None:
			self.raw=b'\x00'*17
		else:
			self.raw=raw
		self.who_byte=None  #Byte
		self.who=None  #Int
		self.content=None  #Int
		self.status=None  #Int
		self.hasPayload=None  #Int
		self.key=None  #Bytes
		self.payload=None  #Bytes
		self.parse()
	def __str__(self):
		return f"""Who Byte: {self.who_byte} ({bin(self.who_byte[0])[2:]:>08})
Key: {self.key}
Payload: {self.payload}
Raw: {self.raw}"""
	def __repr__(self):
		return self.__str__()
	def __len__(self):
		return len(self.raw)

	def payloadLen(self):
		'''Get length of payload, or 0 if none exists'''
		try:
			return len(self.payload)
		except TypeError:
			return 0
	def parse(self):
		'''Parses self.raw'''
		self.who_byte=self.raw[0:1]
		self.parseWho()
		self.key=self.raw[1:17]
		if self.hasPayload:
			self.payload=self.raw[17:]
	def parseWho(self):
		'''Parse self.who_byte'''
		target=self.who_byte[0]
		self.who=target>>7
		self.content=(target>>4)&0b111
		self.status=target>>3&0b1
		self.hasPayload=target>>2&0b1
	def getMessage(self):
		'''Returns a string if this unit has informational content type, error otherwise'''
		if self.content==4 and self.hasPayload:
			return (self.status,self.payload.decode())
		else:
			return None
	def compile(self):
		'''Compile all variables into self.raw.
		Also compiles who_byte'''
		self.raw=b''
		self.compileWho()
		self.raw+=self.who_byte
		self.raw+=self.key
		if self.hasPayload:
			self.raw+=self.payload
	def compileWho(self):
		'''Compiles who variables into who_byte'''
		self.who_byte=self.who<<7
		self.who_byte+=self.content<<4
		self.who_byte+=self.status<<3
		self.who_byte+=self.hasPayload<<2
		self.who_byte&=0b11111100
		self.who_byte=iToB(self.who_byte)
	def setWhoByte(self,new):
		'''Sets who_byte, then parses it'''
		if type(new)==int:
			new=iToB(new)
		self.who_byte=new
		self.parseWho()
	def _setWhoBit(self,new,pos,*,bits=1):
		'''Sets a single bit in the who_byte'''
		new_byte=self.who_byte[0]&~(((2**(bits))-1)<<pos)^(new<<pos)
		self.who_byte=iToB(new_byte)
	def setWho(self,new):
		'''Sets self.who, then updates who_byte'''
		self.who=new
		self._setWhoBit(new,7)
	def setContent(self,new):
		'''Sets self.content, then updates who_byte'''
		self.content=new
		self._setWhoBit(new,4,bits=3)
	def setStatus(self,new):
		'''Sets self.status, then updates who_byte'''
		self.status=new
		self._setWhoBit(new,3)
	def setHasPayload(self,new):
		'''Sets self.hasPayload, then updates who_byte'''
		self.hasPayload=new
		self._setWhoBit(new,2)
	def setPayload(self,new):
		'''Sets self.payload, then updates self.raw by removing an existing payload and appending the new one.
		Note that this function automatically prepends the payload length to the bytes'''
		self.payload=new
		self.raw=self.raw[:17]
		self.raw+=iToB(len(self.payload),2)
		self.raw+=self.payload

class Ports():
	def __init__(self,start=0,end=1024,n=100):
		self.start=start  #Inclusive
		self.end=end  #Exclusive
		self.n=n
		self.pointer=start
	def __iter__(self):
		return self
	def __next__(self):
		'''Returns a list of next n ports'''
		#Make sure n doesn't go past self.end
		if self.pointer==self.end:
			self.pointer=self.end+1
			return b''
		elif self.pointer>self.end:
			raise StopIteration

		if self.pointer+self.n>self.end:
			high=self.end
		else:
			high=self.pointer+self.n

		toret=b''
		for i in range(self.pointer,high):
			toret+=iToB(i,2)
		self.pointer=high
		return toret
#------------#
#    Data    #
#------------#
#Used by server to decode data
handshake_payload_types={0x00:("timeout",bToI),
0x01:("port_start",bToI),
0x02:("port_end",bToI),
0x03:("port_chunk",bToI)}
# 0x04:("delay",lambda d:bToI(p))}
#Used by client to encode data.
#Takes arguments from menuentries
handshake_payload_client={"timeout":(b'\x00',iToB),
"start":(b'\x01',iToB),
"end":(b'\x02',iToB),
"chunk":(b'\x03',iToB)}

#------------------#
#    Misc Funcs    #
#------------------#
def recvUnit(s):
	'''Recv unit from s.
	Returns a unit'''
	try:
		received_data=recvExact(s,17)
		if received_data==b'':  #Couldn't get data
			return None
		toret=Unit(received_data)  #Receive first 17
		if len(toret)<17:
			return None
		#Check for payload
		if toret.hasPayload:
			paylen=bToI(recvExact(s,2))
			toret.payload=recvExact(s,paylen)
		return toret
	except socket.timeout:
		return None
def recvFrom(s,b):
	'''Receive b bytes from s'''
	try:
		return s.recv(b)
	except socket.timeout:
		return None
def recvExact(s,n):
	'''Receive exactly n bytes from s via while loop.
	Returns None if timeout'''
	toret=b''
	target=n
	try:
		while True:
			toret+=s.recv(target)
			if toret==b'':  #Remote closed
				raise RecvError("Remote closed")
			target=n-len(toret)
			if target!=0:
				continue
			else:
				return toret
	except socket.timeout:
		return None


#--------------#
#    Errors    #
#--------------#
class HandshakeError(Exception):
	def __init__(self,status,message):
		super().__init__(f"Error in handshake:[{status}]: {message}")
		self.status=status
		self.message=message
class NotInfoError(Exception):
	def __init__(self):
		super().__init__("Unit isn't informational!")
class RecvError(Exception):
	def __init__(self,message):
		super().__init__(f"Error receiving bytes: {message}")
		self.message=message


if __name__=="__main__":
	unit=Unit()
	unit.setWhoByte(b'\xaa')  #1010 1010
	unit.setStatus(1)
	unit.setHasPayload(0)
	unit.key=b'______test______'
	print(unit)
	unit.setContent(5)
	print(unit)
	print("Who:",unit.who)
	print("Content:",unit.content)
	print("Status:",unit.status)
	print("Has Payload:",unit.hasPayload)
	unit.compile()
	print(unit)
	unit.parseWho()
	print("Who:",unit.who)
	print("Content:",unit.content)
	print("Status:",unit.status)
	print("Has Payload:",unit.hasPayload)
