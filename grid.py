## Author:  Owen Cocjin
## Version: 1.0
## Date:    2021.12.20
## Description:    A small library to create graphical grids in terminal
## Notes:
##  - The terminal using this lib must support ANSI escape sequences, such as Bash
##  - A unit is 3 chars wide by default
##  - The curse_pos of Grid stores the cursor position relative to the grid.
##    The unit size is excluded from this position
## Important:
##  - MoveLinear doesn't calculate the correct position if drawUnit without backstep was used
import time

class Grid():
	def __init__(self, width, height, unit, draw=True):
		self.width=width
		self.height=height
		self.curse_pos=[0,0]  #Cursor position;[horizontal,vertical]
		self.notif_line=0  #Number of notifications that have been called
		self.units={}  #Dict of named units for easy reference
		#Create a unit if one wasn't passed
		if type(unit)!=Unit:
			self.unit=Unit(*unit)
		elif type(unit)==Unit:
			self.unit=unit
		else:  #No unit specified, raise an error
			raise UnitError(f"There was an error creating the unit from ({unit})")
		#Draw grid if requested
		if draw:
			self.enterGrid()

	def drawGrid(self):
		'''Draw grid.
		This assumes we are currently in the alt buffer'''
		for h in range(self.height):
			# printf(f'\033[100m{" "*unit}')
			for w in range(self.width):
				printf(f'\033[0m{self.unit}')
			printf('\n\033[0m')
	def drawPixel(self,colour='\033[42m',offset=0,count=1):
		'''Draws a single pixel (character) in the current position.
		Does not return cursor to previous position'''
		#Move offset
		if offset:
			print(f'\033[{offset}C',end='')
		print(f"{colour}{' '*count}{self.unit.colour}",end='')
	def drawRefUnit(self,ref):
		'''Draws a unit stored in self.units'''
		if ref not in self.units:
			return False
		self.drawUnit(self.units[ref])
	def drawUnit(self, unit=None,backstep=False):
		'''Draws a new unit at current cursor position'''
		if unit==None:
			unit=self.unit
		printf(unit)
		#Move cursor back to original pos
		if backstep:
			printf(f'\033[{unit.size}D')
		else:
			self.curse_pos[0]+=1
	def enterGrid(self):
		'''Sets up the grid, then draws it'''
		printf('\033[?1049h\033[H')
		self.drawGrid()
		self.goTo()
	def exitGrid(self):
		'''Leaves grid and cleans everything up'''
		print('\033[J\033[?1049l')
	def getLeave(self):
		'''Prints an exiting message'''
		self.nnotify("Press [Enter] to finish")
		input()
		self.exitGrid()
	def goTo(self, horizontal=0,vertical=0):
		'''Moves cursor to a specific unit'''
		if horizontal>self.width-1:
			horizontal=self.width-1
		if vertical>self.height-1:
			vertical=self.height-1
		printf(f'\033[H\033[{vertical+1};{(horizontal*self.unit.size)+1}H')
		self.curse_pos[0]=horizontal
		self.curse_pos[1]=vertical
	def move(self, horizontal=0,vertical=0):
		'''Moves cursor relative to current position.
		Accepts negative numbers'''
		#Check if movement puts us over width and/or height
		#If they are, don't move
		if horizontal+self.curse_pos[0]>self.width-1:
			horizontal=0
		if vertical+self.curse_pos[1]>self.height-1:
			vertical=0
		#Convert to directions
		if horizontal<0:
			printf(f'\033[{-horizontal*self.unit.size}D')
		elif horizontal:
			printf(f'\033[{horizontal*self.unit.size}C')
		if vertical<0:
			printf(f'\033[{-vertical}A')
		elif vertical:
			printf(f'\033[{vertical}B')
		#Update cursor pos
		self.curse_pos[0]+=horizontal
		self.curse_pos[1]+=vertical
	def moveLinear(self,move):
		'''Moves along the grid as if it was a line.
		Good for creating a grid of increasing integers.
		True axis means horizontal, False means vertical.
		Doesn't account for move==0'''
		#Convert move ammount to x/y
		calc=move+self.curse_pos[0]
		y=((self.curse_pos[1]+(calc//self.width))%self.height)-self.curse_pos[1]
		x=(calc%self.width)-self.curse_pos[0]

		self.move(x,y)
		return (x,y)
	def notify(self,message,colour='\033[43m',line=0):
		'''Prints a message at the bottom of the grid'''
		#Move cursor to bottom
		printf(f'\033[H\033[{self.height+line}B')
		self.notif_line=line
		#Print message
		printf(f"{colour}{message}\033[0m\033[K")
	def nnotify(self,message,colour='\033[43m'):
		'''Prints a message at the bottom of the grid.
		Automatically goes to next notif line'''
		#Essentially jsut a wrapper for self.notify
		self.notify(message,colour,line=self.notif_line+1)
	def reset(self):
		'''Resets grid'''
		printf('\033[2J\033[H')
		self.drawGrid()
	def write(self,text,backstep=False):
		'''Writes text in default unit'''
		self.drawUnit(Unit(self.unit.size,content=text))
		if backstep:
			self.moveLinear(-1)
class Unit():
	def __init__(self, size, colour='\033[100m', content=''):
		'''Defines a single unit'''
		self.size=size
		self.colour=colour
		self.content=str(content)
	def __str__(self):
		return self.drawUnit()
	def __repr__(self):
		return self.__str__()
	def drawUnit(self):
		'''Prints a unit'''
		content_length=self.size-len(self.content)
		l=r=content_length//2
		if content_length%2==1:
			r+=1
		#Print the unit
		return f"{self.colour}{' '*l}{self.content}{' '*r}\033[0m"

#--------------#
#    Errors    #
#--------------#
class UnitError(Exception):
	def __init__(self, message):
		Exception.__init__(self, message)

def printf(*args,**kwargs):
	kwargs["flush"]=True
	kwargs["end"]=''
	print(*args,**kwargs)

if __name__=="__main__":
	S=6  #Unit size
	g=Grid(7,15,Unit(S, content='a'),draw=True)
	try:
		g.units["green"]=Unit(S, '\033[42m', 'b')
		g.goTo()

		#Diagonal green
		time.sleep(1)
		for i in range(20):
			g.drawRefUnit("green")
			time.sleep(0.03)
			g.move(1,1)
		g.reset()

		#moveLinear
		g.goTo()
		for i in range(g.width*g.height):
#f"{g.curse_pos[0]}:{g.curse_pos[1]}"
			g.drawUnit(Unit(S,'\033[42m',f"{g.curse_pos[0]}:{g.curse_pos[1]}"))
			time.sleep(0.03)
			g.moveLinear(1)

		#moveLinear overflow
		time.sleep(1)
		g.goTo(g.width-2,2)
		g.drawUnit(Unit(S,'\033[43m',f"{g.width-2}:{2}"))
		time.sleep(1)
		prev=g.moveLinear(5)
		g.drawUnit(Unit(S,'\033[43m',f"{prev[0]}-{prev[1]}"))
		time.sleep(1)

		#Print numbers with linear move>width
		prev=(0,0)
		g.goTo()
		for i in range(g.width*g.height-1):
			g.drawUnit(Unit(S,'\033[44m',f"{prev[0]}-{prev[1]}"))
			time.sleep(0.05)
			prev=g.moveLinear(4)

		time.sleep(3)
		g.exitGrid()
	except KeyboardInterrupt:
		g.exitGrid()
