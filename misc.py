## Author:  Owen Cocjin
## Version: 0.1
## Date:    2021.12.10
## Description:    Misc functions
## Notes:
def bToI(b):
	'''Returns an int'''
	toret=0
	for i in b:
		toret=(toret<<8)+i
	return toret
def iToB(i,length=1):
	'''Returns a bytes object'''
	h=hex(i)[2:]
	if len(h)%2==1:
		h=f"0{h}"  #Add 0 for stupid bytes object
	#Add padding zeros if length!=None
	toret=bytes.fromhex(h)
	cur_length=len(toret)
	if cur_length<length:
		toret=b'\x00'*(length-cur_length)+toret
	return toret
