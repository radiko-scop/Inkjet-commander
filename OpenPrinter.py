#Oasis controller is the software used to control the HP45 and GRBL driver in Oasis
#Copyright (C) 2018  Yvo de Haas

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


import sys
import glob

from PyQt5 import uic
from PyQt5.QtWidgets import QApplication
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QFileDialog
from PyQt5.QtWidgets import QMessageBox, QComboBox, QLabel
from PyQt5.QtGui import QPixmap, QColor, QImage
from SerialHP45 import HP45
from OPSerialGRBL import GRBL
import os
from ImageConverter import ImageConverter
from ImageConverter2 import ImageSlicer
import B64
from numpy import *
import time
import serial

import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()

        Form, Window = uic.loadUiType("OpenPrinter.ui")

        self.ui = Window()
        self.form = Form()
        self.form.setupUi(self.ui)
        self.ui.show()


        self.inkjet = HP45()
        self.grbl = GRBL()
        self.imageconverter = ImageConverter()

        self.printing_state = 0 #whether the printer is printing

        self.RefreshPorts() #get com ports for the buttons

        self.error_counter = 0

        self.form.inkjet_refresh.clicked.connect(self.RefreshPorts)


        #inkjet connect button
        self.inkjet_connection_state = 0 #connected state of inkjet
        self.form.inkjet_connect.clicked.connect(self.InkjetConnect)

        #inkjet function buttons
        self.form.inkjet_preheat.clicked.connect(self.InkjetPreheat)
        self.form.inkjet_prime.clicked.connect(self.InkjetPrime)
        self.form.dpi_combo.currentIndexChanged.connect(self.InkjetSetDPI)
        self.form.inkjet_set_density.clicked.connect(self.InkjetSetDensity)
        self.form.inkjet_test_button.clicked.connect(self.inkjet.TestPrinthead)
        self.form.button_clear_buffer.clicked.connect(self.inkjet.ClearBuffer)
        self.form.button_reset_buffer.clicked.connect(self.inkjet.ResetBuffer)
        self.form.buffer_mode_combo.currentIndexChanged.connect(self.InkjetBufferMode)
        self.form.side_combo.currentIndexChanged.connect(self.InkjetSideMode)
        self.form.serial_send_button.clicked.connect(self.InkjetSendCommand)
        self.form.serial_send_line.returnPressed.connect(self.InkjetSendCommand)

        #file buttons
        self.file_loaded = 0
        self.form.file_open_button.clicked.connect(self.OpenFile)
        self.form.inkjet_send_image.clicked.connect(self.printImage)
        #self.form.inkjet_send_image.clicked.connect(self.PrintButtonClicked)


    def RefreshPorts(self):
        """ Lists serial port names
        :raises EnvironmentError:
            On unsupported or unknown platforms
        """
        if sys.platform.startswith('win'):
            ports = ['COM%s' % (i + 1) for i in range(256)]
        elif sys.platform.startswith('linux') or sys.platform.startswith('cygwin'):
            # this excludes your current terminal "/dev/tty"
            ports = glob.glob('/dev/tty[A-Za-z]*')
        elif sys.platform.startswith('darwin'):
            ports = glob.glob('/dev/tty.*')
        else:
            raise EnvironmentError('Unsupported platform')

        result = []
        for port in ports:
            try:
                s = serial.Serial(port)
                s.close()
                result.append(port)
            except (OSError, serial.SerialException):
                pass
        #print(result)

        #update the com ports for motion and inkjet
        self.form.inkjet_set_port.clear()
        self.form.inkjet_set_port.addItems(result)
        self.form.grbl_set_port.clear()
        self.form.grbl_set_port.addItems(result)

    def InkjetConnect(self):
        """Gets the inkjet serial port and attempt to connect to it"""
        if (self.printing_state == 0): #only act on the button if the printer is not printing
            if (self.inkjet_connection_state == 0): #get connection state, if 0 (not connected)
                #print("Attempting connection with HP45")
                temp_port = str(self.form.inkjet_set_port.currentText()) #get text
                inkjet_connected = self.inkjet.Connect(temp_port) #attempt to connect
                grbl_port = str(self.form.grbl_set_port.currentText()) #get text
                if grbl_port != temp_port:
                    grbl_connected = self.grbl.Connect(grbl_port)
                    if not grbl_connected:
                        logger.warn("GRBL is not connected - no motion available")
                if (inkjet_connected): #on success,
                    self.form.inkjet_connect.setText("Disconnect") #rewrite button text
                    self.inkjet_connection_state = 1 #set  state
                else:
                    logger.error("Connection with HP cardridge failed")
            else: #on state 1
                #print("disconnecting from HP45")
                self.inkjet.Disconnect() #disconnect
                self.grbl.Disconnect()
                self.inkjet_connection_state = 0 #set state to disconnected
                self.form.inkjet_connect.setText("Connect") #rewrite button

    def InkjetSendCommand(self):
        """Gets the command from the textedit and prints it to Inkjet"""
        if (self.inkjet_connection_state == 1):
            temp_command = str(self.form.serial_send_line.text())#get line
            temp_command += "\r" #add end of line
            self.inkjet.SerialWriteBufferRaw(temp_command) #write to inkjet
            self.form.serial_send_line.clear() #clear line

    VIRTUAL_VELOCITY=1
    def printImage(self):
        self.inkjet.SetPrintMode(self.VIRTUAL_VELOCITY)
        self.print_velocity = 10
        self.inkjet.SetVirtualVelocity(self.print_velocity)
        self.inkjet.SetTriggerPosition(0)
        self.inkjet.VirtualEnable()
        self.PrintArray2(1)
        #self.inkjet.SerialStop()

    def InkjetSetPosition(self):
        """Gets the position from the textbox and converts it and sends it to HP45"""
        if (self.inkjet_connection_state == 1 and self.printing_state == 0): #only act on the button if the printer is not printing and connected
            temp_pos = self.form.encoder_position.text() #set pos to variable
            try:
                temp_pos = float(temp_pos)
                print("Setting position to: " + str(temp_pos))
                temp_pos *= 1000.0
                temp_pos = int(temp_pos) #cast to intergers
            except:
                print("Value could not be converted")
                return
            self.form.encoder_position.setText("")
            self.inkjet.SetPosition(temp_pos) #set position

    def InkjetVirtualVelocity(self):
        """Set the printhead to the given virtual velocity in mm/s (float)"""
        if (self.inkjet_connection_state == 1 and self.printing_state == 0): #only act on the button if the printer is not printing and connected
            temp_vel = self.form.virtual_velocity.text() #set pos to variable
            try:
                temp_vel = float(temp_vel)
                print("Setting virtual velocity to: " + str(temp_vel))
                #temp_vel *= 1000.0
                temp_vel = int(temp_vel) #cast to intergers
            except:
                print("Value could not be converted")
                return
            #self.form.virtual_velocity.setText("")
            self.inkjet.SetVirtualVelocity(temp_vel) #set position

    def InkjetSetTriggerPosition(self):
        """Set the trigger position, the position the printhead moves to when the trigger is given"""
        if (self.inkjet_connection_state == 1 and self.printing_state == 0): #only act on the button if the printer is not printing and connected
            temp_vel = self.form.trigger_reset_position.text() #set pos to variable
            try:
                temp_vel = float(temp_vel)
                print("Setting trigger position to: " + str(temp_vel))
                temp_vel *= 1000.0
                temp_vel = int(temp_vel) #cast to intergers
            except:
                print("Value could not be converted")
                return
            #self.form.trigger_reset_position.setText("")
            self.inkjet.SetTriggerPosition(temp_vel) #set position

    def InkjetUpdateTriggerMode(self):
        """Ask for the trigger mode for the given pin and update the value of the box to the current value"""
        print("InkjetUpdateTriggerMode Not implemented")

    def InkjetBufferMode(self): #sets what mode the buffer resets at
        temp_mode = self.form.buffer_mode_combo.currentIndex ()
        self.inkjet.BufferMode(temp_mode)
        #print(temp_mode)

    def InkjetSideMode(self): #sets what side can and cannot print
        temp_mode = self.form.side_combo.currentIndex ()
        self.inkjet.SetSideMode(temp_mode)
        print(temp_mode)

    def InkjetPrime(self):
        """if possible, sends a priming burst to the printhead"""
        if (self.inkjet_connection_state == 1 and self.printing_state == 0): #only act on the button if the printer is not printing and connected
            self.inkjet.Prime(100)


    def InkjetPreheat(self):
        """if possible, sends a preheating burst to the printhead"""
        if (self.inkjet_connection_state == 1 and self.printing_state == 0): #only act on the button if the printer is not printing and connected
            self.inkjet.Preheat(5000)

    def InkjetSetDPI(self):
        """Writes the DPI to the printhead and decode function"""
        #temp_dpi = str(self.form.inkjet_dpi.text()) #get text#get dpi
        #print("Setting DPI")
        temp_dpi = str(self.form.dpi_combo.currentText()) #get dpi
        temp_dpi = temp_dpi.partition(' ')
        temp_dpi = temp_dpi[0]
        temp_dpi_val = 0
        #print(temp_dpi)
        temp_success = 0
        try:
            temp_dpi_val = int(temp_dpi)
            temp_success = 1
        except:
            print ("Unable to set dpi")
            nothing = 0

        if (temp_success == 1): #if conversion was successful
            if (self.printing_state == 0): #only set DPI when not printing
                print("DPI to set: " + str(temp_dpi_val))
                if (self.inkjet_connection_state == 1): #only write to printhead when connected
                    self.inkjet.SetDPI(temp_dpi_val) #write to inkjet
                self.imageconverter.SetDPI(temp_dpi_val) #write to image converter
                if (self.file_loaded != 0): #if any file is loaded
                    print("resising image")
                    self.OpenFile(self.input_file_name[0])

    def InkjetSetDensity(self):
        """Writes the Density to the printhead"""
        if (self.inkjet_connection_state == 1):
            temp_density = str(self.form.inkjet_density.value()) #get text #get density
            temp_density_val = 0
            temp_success = 0
            try:
                temp_density_val = int(temp_density)
                temp_success = 1
            except:
                #print ("Unable to convert to dpi")
                nothing = 0

            if (temp_success == 1): #if conversion was successful
                #print("Density to set: " + str(temp_density_val))
                temp_density_val = temp_density_val * 10 #multiply by 10 because interface handles this value from 1-100
                print(temp_density_val)

                self.inkjet.SetDensity(temp_density_val) #write to inkjet


    def OpenFile(self, temp_input_file = ""):
        """Opens a file dialog, takes the filepath, and passes it to the image converter"""
        if (temp_input_file):
            self.imageSlicer = ImageSlicer(temp_input_file)
        else:
            self.input_file_name = QFileDialog.getOpenFileName(self, 'Open file',
            '',"Image files (*.jpg *.png *.svg)")
            self.imageSlicer = ImageSlicer(self.input_file_name[0])
        #self.RenderInput()
        #self.RenderOutput()
        self.file_loaded = 1

    def RenderInput(self):
        """Gets an image from the image converter class and renders it to input"""
        height, width, channel = self.imageSlicer.image().shape
        bytesPerLine = channel * width
        print(f"Rendering input {height}, {width}, {channel}, {bytesPerLine}")
        self.input_image_display = QPixmap(QImage(self.imageSlicer.image().data, width, height, bytesPerLine, QImage.Format_RGBA8888))
        if (self.input_image_display.width() > 200 or self.input_image_display.height() > 200):
            self.input_image_display = self.input_image_display.scaled(200,200, QtCore.Qt.KeepAspectRatio)
        self.form.output_window.setPixmap(self.input_image_display)



    def RenderOutput(self):
        """Gets an image from the image converter class and renders it to output"""
        height, width = self.imageSlicer.output().shape
        gray = self.imageSlicer.output()
        channel = 1
        bytesPerLine = channel * width
        print(f"Rendering input {height}, {width}, {channel}, {bytesPerLine}")
        self.input_image_display = QPixmap(QImage(gray.data, width, height, bytesPerLine, QImage.Format_Grayscale8))
        if (self.input_image_display.width() > 200 or self.input_image_display.height() > 200):
            self.input_image_display = self.input_image_display.scaled(200,200, QtCore.Qt.KeepAspectRatio)
        self.form.output_window.setPixmap(self.input_image_display)


    def PrintButtonClicked(self):
        """Print button clicked, get variables and print the array"""
        temp_pos = 10.0

        #get the starting position from the menu
        if (self.inkjet_connection_state == 1): #only act on the button if the printer is not connected
            try:
                temp_pos = self.form.image_start_position.text() #set pos to variable
                temp_pos = float(temp_pos)
                print("Starting position is: " + str(temp_pos))
                temp_pos = int(temp_pos) #cast to intergers
            except:
                print("Value could not be converted, defaulting to 10mm")

            #send the print command
            self.PrintArray(temp_pos)


    def _computePosition(self, index):
        """return position of pixel line with index index, as a properly formatted B64 string
        """
        pos = ((index) * self.pixel_to_pos_multiplier) + self.y_start_pos
        pos *= 1000 #printhead pos is in microns
        return B64.B64ToSingle(pos) #make position value

    def _createSweepsBuffers(self):
        self.sweepsBuffers = []
        sweep_index = 0
        for sweep in self.imageSlicer.imageSweeps():
            index = 0
            line_commands = []
            logger.debug(f"Processing sweep {sweep_index}, lines in sweep : {len(sweep)}")
            for line in sweep:
                line_position = self._computePosition(index)
                b64_line = B64.B64ToArray(line)
                command = f"SBR {line_position} {b64_line}"
                line_commands += [command]
                index += 1
            self.sweepsBuffers += [line_commands]

            # #Finish with one line closing all nozzles
            # b64_line = B64.B64ToArray(zeros(self.imageSlicer.dpi()//2))
            # line_position = self._computePosition(index+1)
            # command = f"SBR {line_position} {b64_line}"
            sweep_index += 1

    def PrintArray2(self, temp_start_position):
        """Prints the current converted image array, only works if both inkjet and motion are connected"""
        self.pixel_to_pos_multiplier = 25.4 / self.imageSlicer.dpi()
        self.y_start_pos = temp_start_position
        self.y_acceleration_distance = 25.0
        self._createSweepsBuffers()
        self.grbl.setZeros()
        logger.debug(f"SweepCount:{len(self.sweepsBuffers)}")
        index = 0
        for sweep in  self.sweepsBuffers:
            x = self.pixel_to_pos_multiplier*len(sweep) + 10
            y = -self.pixel_to_pos_multiplier*index*self.imageSlicer.dpi()/2
            self.grbl.asyncMove(0, y, self.print_velocity)
            self.grbl.waitMotionEnd()
            line_duration = self.pixel_to_pos_multiplier*len(sweep) / self.print_velocity # mm / mm/s = s
            for line in sweep:
                print(f"Sending {line}")
                self.inkjet.SerialWriteBufferRaw(line)
            self.grbl.asyncMove(x, y, self.print_velocity)
            self.inkjet.SerialTrigger()
            # left = self.inkjet.BufferLeft()
            # while(left >0):
            #     left = self.inkjet.BufferLeft()
            #     print(f"Waiting empty buffer ({left} left).")
            #     time.sleep(0.1)
            self.grbl.waitMotionEnd()
            self.grbl.asyncMove(0, y, self.print_velocity*4)
            self.grbl.waitMotionEnd()
            index += 1
        self.grbl.asyncMove(0, y, self.print_velocity*4)
        self.grbl.waitMotionEnd()
        self.grbl.asyncMove(0, 0, self.print_velocity*4)
        self.grbl.waitMotionEnd()


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    gui = MainWindow()
    sys.exit(app.exec_())
    # gui.OpenFile(temp_input_file="ytec_logo_icon.png")
    # gui.RenderOutput()
    # gui.PrintArray2(1)

