## Author:  Owen Cocjin
## Version: 0.3
## Date:    2023.04.25
## Description:    Menu entries for progmenu
## Notes:
## Updates:
##  - Added -o
from progmenu import EntryArg,EntryFlag
from os.path import isfile

def toIFunc(i):
	'''Converts entry to int'''
	return int(i)
def outfileFunc(o):
	'''Writes results to a file'''
	if isfile(o):
		print(f"\033[93m[|X:menuentries:outfileFunc]\033[0m: The file {o} exists! Overwrite (Y/n)? ", end='')
		if input().lower() not in ['','y',"yes"]:
			print(f"[|X:menuentries:outfileFunc]: Can't continue with given file!")
			exit()  #Not sure if this is bad practice to exit here lol
	return o

def helpFunc():
	print("""dropdetector.py [-cdehiopst]
* Tests if a network is dropping packets, or interfering in any way *
  -c; --chunk=<c>:   Number of ports to test per socket (default 100)
  -d; --delay=<d>:   Seconds to wait between failed connections (default 1).
                     Can be a float
  -e; --end=<e>:     End of port range (default 1025); Exclusive
  -h; --help:        Prints this page
  -i; --ip=<i>:      Server IP (default 0.0.0.0)
  -o; --output=<o>:  Save results to file <o>
  -p; --port=<p>:    Data port (default 8080).
                     This port MUST NOT be blocked
  -s; --server:      Run as server
  -t; --timeout=<t>: Socket timeout in seconds (default 3 seconds)
  -r; --start=<s>:   Start of port range (default 1); Inclusive

  Graph info:
    - ACPT: Accepted packets.
            This is reliable as the server must confirm the client's ID
    - CLOSE: Closed packets.
             The client could connect to the server, but the port was closed.
    - DROP: Dropped packets.
            The socket timedout.
            This could trigger false positives if the timeout is too low!
    - SRVERR: Server Error
              The client connected to the server, but gave an incorrect reply.
              Generally means the socket is in use by another application.

  Notes:
    - The number of threads spawned is largely (entirely) dependent on the chunk size vs the total number of ports.
      Ex: With a port range of 100-210, and a chunk size of 50, this will spawn 3 threads:
          100-149, 150-199, 200-209
    - Setting too short of a delay or timeout will trigger false negatives/positives and can cause unpredictable behaviour.
      Too low of a delay will cause falsely closed ports.
      Too low of a timeout will cause SRVERRs and ultimately hangs the client.
      In localhost testing, a delay<0.6 or a timeout<2 triggers these errors
    - Setting too big of a delay will cause the 
    - Setting too big of a port range (such as ~40k) will cause a severe desync of ports
    - The reason the end port is excluded is because it's just a lot cleaner when excluding it""")

	return True

EntryArg("chunk",['c',"chunk"],toIFunc,default=100)  #Number of ports per transmission
EntryArg("delay",['d',"delay"],lambda d:float(d),default=1)  #Delay between port fails
EntryArg("end",['e',"end"],lambda e:int(e),default=1025)  #End of port range
EntryFlag("help",['h',"help"],helpFunc)  #Help page
EntryArg("ip",['i',"ip"],lambda i:str(i),default="0.0.0.0")  #IP of server
EntryArg("port",['p',"port"],toIFunc,default=8080)  #Data port
EntryFlag("server",['s',"server"],lambda *_:True)  #If this is a server
EntryArg("start",['r',"start"],toIFunc,default=1)  #Start of port range
EntryArg("timeout",['t',"timeout"],toIFunc,default=3)  #Port timeout
EntryArg("outfile",['o',"output"],outfileFunc,default=None)  #Output file
