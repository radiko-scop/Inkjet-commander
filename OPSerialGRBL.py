#This file is part of Oasis controller.

#Oasis controller is free software: you can redistribute it and/or modify
#it under the terms of the GNU General Public License as published by
#the Free Software Foundation, either version 3 of the License, or
#(at your option) any later version.

#Oasis controller is distributed in the hope that it will be useful,
#but WITHOUT ANY WARRANTY; without even the implied warranty of
#MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#GNU General Public License for more details.

#You should have received a copy of the GNU General Public License
#along with Oasis controller.  If not, see <https://www.gnu.org/licenses/>.



#The Serial GRBL class handles all levels of comunications to the GRBL
#controller
#Todo:
#-error lock, stop sending code if errors occur
#-add get and set grbl $ settings
#-check settings to list of required settings
#-auto set settings if different
#-add endstops to pistons, not to home, but to check end (0) reached
#-Change new layer so the last motion is always up, to increase repeatability

import serial
import time
import re

class GRBL(serial.Serial):
    def __init__(self):
        self.ser = serial.Serial() #make an instance of serial connection
        self.ser.baudrate = 115200 #set baudrate
        self.ser.timeout = 0 #set timeout to 0, non blocking mode

        self.grbl_version = 0.0 #version of grbl

    def getNextLine(self):
        """Get next readable line

        Returns:
            _type_: _description_
        """
        received = ""
        while True:
            received += self.ser.read(1).decode('utf-8')
            if len(received) > 0 and received[-1]=="\n":
                break
       # print(f"got : {received.strip("\n").strip("\r")}")
        return received.strip("\n").strip("\r")

    def Connect(self, serial_port):
        """Attempt to connect to the GRBL controller"""
        self.com_port_raw = str(serial_port) #get value from set_com
        self.ser.port = self.com_port_raw #set com port .
        self.ser.open()
        emptyline = self.getNextLine()
        self.grbl_version = re.findall("Grbl ([0-9\.]*)h.*", self.getNextLine())[0]
        if(self.grbl_version != "1.1"):
            raise Exception("Unknown Grbl version -> timid")
        self.ser.write(b"$$\n")
        self.config = []
        while True:
            confline = self.getNextLine()
            if confline != "ok" and confline != "":
                self.config += [confline]
            else:
                break
        return True

    def asyncMove(self, x, y, mm_s):
        print("move")
        mm_min = mm_s *60
        self.sendCommand(f"G1 X{x} Y{y} F{mm_min}")
        print("endmove")

    def setZeros(self):
        self.sendCommand("G10 P0 L20 X0")
        self.sendCommand("G10 P0 L20 Y0")

    def sendCommand(self, command, okayed = True):
        self.ser.write(f"{command}\n".encode('utf-8'))
        if(okayed):
            ok = self.getNextLine()
            if not "ok" in ok:
                raise Exception(f"Error in command:{ok}")

    def status(self):
        self.ser.write(b"?\n")
        status = self.getNextLine()
        ok = self.getNextLine()
        return status

    def waitMotionEnd(self):
        while not "Idle" in self.status():
            print(f"status: {self.status()}")
            time.sleep(0.5)

    def Disconnect(self):
        """close the connection to GRBL"""
        self.ser.close()


if __name__ == '__main__':
    printer = GRBL()
    printer.Connect("/dev/ttyUSB0")
    printer.asyncMove(-10, 0, 10)
    printer.waitMotionEnd()




#messages expected:
#Grbl 1.1f ['$' for help] #initial welcome
#[MSG:'$H'|'$X' to unlock] #unlock message
#ok
#error:#
#<Idle|WPos:0.000,250.000,0.000|Bf:15,127|FS:0,0>
