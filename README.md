#DropDetector
> Confirms if a network is blocking ports, either rejecting or dropping them

## Installation:
Plug n' play! Download the repo and run `main.py`!

#Usage:
Most configuration is done by the client side. This script is meant to test network configurations, so control over a remote server is expected.
On the server, run:
```
python main.py -s
```
On the client, to run with default settings, run:
```
python main.py -i <ip of server>
```
This will display a graph on the client and start making connections. The default parameters are to scan ports 1-1023 with a chunk size of 100. All defaults can be found in the help menu `python main.py -h`. The client will inform you when it's done.

## Notes:
- Testing on localhost is somewhat unstable when scanning ports >=1024. This is due to the fact that any non-well-known port is considered ephemeral and the client may use the same port it's trying to test.
- If testing on localhost, ports >=1024 may cause false "closed" results due to the kernel assigning the client an ephemeral port that the server is trying to scan.
- If testing ports <=1023, the **SERVER** must be run as root (as it must open well-known ports)
- The number of threads used is directly related to the size of the chunks vs the total ports scanned

## Shortcomings:
- If one of either client/server stops without warning, there is no way for the other to tell the connection has been lost. This will be fixed by converting the data port to a heartbeat port after complete handshake.

## Future Implemetations:
- Of all the results, print only the smallest ones (ex. If there are 2 dropped and 998 acceptes, only print the dropped ports)
- Add a heartbeat to the data port to prevent messy, accidental kills

## Current Bugs:

### Client
- ~~**[cli.01]**: Client crashes when scanning a server that is actively using port 443~~ **Fixed**: Caught error and return to client as srverr.
- ~~**[cli.02]**: Somewhat commonly, the client will spit out an "Index out of range" error while parsing the who_byte, indicating it didn't receive any data from the server. This error was found when scanning port 443 while it was occupied by an Apache server. I believe the error is caused by the server simply closing the bad connection (?).~~ **Fixed**: Before data.recvUnit (which caused the error) converts the bytes to Unit, check if it received an empty byte. This indicates a closed remote socket, so return None and allow caller to handle.

### Server
- ~~**[srv.01]**: Using too high of a chunk size causes threads to crash (due to an overflow-like bug). This is caused by the break of data during transmission. The server sends (or client receives) what should be one unit, as 2 distinct units, causing an invalid who byte for the second unit, followed by a crash. The client detects an invalid port response and abruptly closes the data port. Instead, the client can send a retry message which will allow the server to resend the data.~~ **Fixed**: Due to TCP breaking packets apart during transmission, client only received partial units. Created a function to receive exactly N bytes from server to ensure full unit transmission.

### Generic
- **[gen.01]**: Because the program is so loud/aggressive, excessive use may cause firewalls to block traffic
