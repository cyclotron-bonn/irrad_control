#include <Wire.h> //i2c
#include "ArdSer.h" //Serial-Comm

interface _intf;
/*
 * Initialize global variables and arrays
 * 
 * -> what to do
 * -> i2c address of slave device
 * -> register of i2c device
 * -> 8 bit ints for data sent via i2c
 */


uint8_t RO_ADDRESS;
String command;
uint8_t address;
uint8_t data;

void setup() {
  /*
   * initiliaze i2c commication as master
   * initialize Serial communication with baudrate Serial.begin(<baudrate>)
   * delay 500ms to let connections and possible setups to be established
   */
  Wire.begin();
  Serial.begin(115200); 
  delay(500);
  
}

uint8_t writeData(uint8_t _reg, uint8_t _data){
  /*
   * transmit data via i2c to device on RO_ADDRESS
   * write register _reg to be written on and write _data on it
   * end transmission and return the errorcode (0 is success) see documentation for further info
   */
  Wire.beginTransmission(RO_ADDRESS);
  Wire.write(_reg);
  Wire.write(_data);
  return Wire.endTransmission();
}

uint8_t readData(uint8_t _reg){
  /*
   * read data via i2c from device in RO_ADDRESS
   * write register to be read from
   * request data from device
   * read the received data from device RO_ADDRESS register _reg and return it
   */
  Wire.beginTransmission(RO_ADDRESS);
  Wire.write(_reg);
  Wire.endTransmission();
  Wire.requestFrom(RO_ADDRESS, 0x1U); //request 1 byte (Unsigned) from Adress RO_ADDRESS
  return Wire.read();
}

void loop() {
  uint8_t _transErr;
  if(Serial.available()){
    _intf.receive();

    command = _intf.arg1;
    address = _intf.arg2.toInt();
    data = _intf.arg3.toInt();

    /*
     * execute command i.e. read/write data, check connection or change i2c device address
     */
    if(command == "T"){
      Wire.beginTransmission(RO_ADDRESS);
      _transErr = Wire.endTransmission();
      _intf.transmit(String(_transErr));
    }
    if(command == "R"){
      _intf.transmit(String(readData(address)));
    }
    if(command == "W"){
      _intf.transmit(String(writeData(address, data)));
    }
    if(command == "A"){
      RO_ADDRESS = address;
      _intf.transmit(String(RO_ADDRESS));
    }
  }
  /*
   * delay 100µs between cycles
   */
  delayMicroseconds(100);
}
