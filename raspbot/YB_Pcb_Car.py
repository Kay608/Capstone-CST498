#!/usr/bin/env python
# coding: utf-8
import smbus
import time
import math
class YB_Pcb_Car(object):

    def get_i2c_device(self, address, i2c_bus):
        self._addr = address
        if i2c_bus is None:
            return smbus.SMBus(1)
        else:
            return smbus.SMBus(i2c_bus)

    def __init__(self):
        # Create I2C device.
        self._device = self.get_i2c_device(0x16, 1)

    def write_u8(self, reg, data):
        try:
            self._device.write_byte_data(self._addr, reg, data)
        except:
            print ('write_u8 I2C error')

    def write_reg(self, reg):
        try:
            self._device.write_byte(self._addr, reg)
        except:
            print ('write_u8 I2C error')

    def write_array(self, reg, data):
        try:
            # self._device.write_block_data(self._addr, reg, data)
            self._device.write_i2c_block_data(self._addr, reg, data)
        except:
            print ('write_array I2C error')

    def Ctrl_Car(self, l_dir, l_speed, r_dir, r_speed):
        try:
            reg = 0x01
            data = [l_dir, l_speed, r_dir, r_speed]
            self.write_array(reg, data)
        except:
            print ('Ctrl_Car I2C error')
            
    def Control_Car(self, speed1, speed2):
        try:
            if speed1 < 0:
                dir1 = 0
            else:
                dir1 = 1
            if speed2 < 0:
                dir2 = 0
            else:
                dir2 = 1 
            
            self.Ctrl_Car(dir1, int(math.fabs(speed1)), dir2, int(math.fabs(speed2)))
        except:
            print ('Ctrl_Car I2C error')


    def Car_Run(self, speed1, speed2):
        try:
            self.Ctrl_Car(1, speed1, 1, speed2)
        except:
            print ('Car_Run I2C error')

    def Car_Stop(self):
        try:
            reg = 0x02
            self.write_u8(reg, 0x00)
        except:
            print ('Car_Stop I2C error')

    def Car_Back(self, speed1, speed2):
        try:
            self.Ctrl_Car(0, speed1, 0, speed2)
        except:
            print ('Car_Back I2C error')

    def Car_Left(self, speed1, speed2):
        try:
            self.Ctrl_Car(0, speed1, 1, speed2)
        except:
            print ('Car_Spin_Left I2C error')

    def Car_Right(self, speed1, speed2):
        try:
            self.Ctrl_Car(1, speed1, 0, speed2)
        except:
            print ('Car_Spin_Left I2C error')

    def Car_Spin_Left(self, speed1, speed2):
        try:
            self.Ctrl_Car(0, speed1, 1, speed2)
        except:
            print ('Car_Spin_Left I2C error')

    def Car_Spin_Right(self, speed1, speed2):
        try:
            self.Ctrl_Car(1, speed1, 0, speed2)
        except:
            print ('Car_Spin_Right I2C error')

    def Ctrl_Servo(self, id, angle):
        try:
            reg = 0x03
            data = [id, angle]
            if angle < 0:
                angle = 0
            elif angle > 180:
                angle = 180
            self.write_array(reg, data)
        except:
            print ('Ctrl_Servo I2C error') 

    def Ctrl_Buzzer(self, frequency, duration):
        """
        Control the buzzer on the Yahboom Raspbot.
        
        Args:
            frequency (int): Frequency of the buzz (0-255, higher = higher pitch)
            duration (int): Duration in milliseconds (0-65535)
        """
        try:
            reg = 0x04  # Typical buzzer register for Yahboom robots
            # Convert duration from milliseconds to appropriate format (divide by 10 for timing)
            duration_val = min(255, max(0, duration // 10))
            frequency_val = min(255, max(0, frequency))
            data = [frequency_val, duration_val]
            self.write_array(reg, data)
        except:
            print('Ctrl_Buzzer I2C error')
    
    def Buzz_Short(self):
        """Play a short recognition buzz sound."""
        self.Ctrl_Buzzer(200, 200)  # Medium frequency, 200ms duration
    
    def Buzz_Success(self):
        """Play a success pattern buzz sound."""
        self.Ctrl_Buzzer(150, 100)   # Lower pitch, short
        time.sleep(0.15)
        self.Ctrl_Buzzer(200, 100)   # Medium pitch, short  
        time.sleep(0.15)
        self.Ctrl_Buzzer(250, 150)   # Higher pitch, longer
    
    def Buzz_Alert(self):
        """Play an alert/warning buzz sound."""
        self.Ctrl_Buzzer(255, 100)   # High pitch, short
        time.sleep(0.1)
        self.Ctrl_Buzzer(255, 100)   # High pitch, short
        time.sleep(0.1)
        self.Ctrl_Buzzer(255, 200)   # High pitch, longer 
