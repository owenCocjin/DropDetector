## Author:  Owen Cocjin
## Version: 0.1
## Date:    2021.12.10
## Description:    Payload management functions
## Notes:
from misc import iToB,bToI

def parseTimeout(d):
	'''Returns an int representing the number of seconds to wait before socket timeout'''
	return bToI(d)
