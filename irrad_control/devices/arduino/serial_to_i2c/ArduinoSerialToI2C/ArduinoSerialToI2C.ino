#include <Wire.h> //i2c

/*
 * Initialize global variables and arrays
 * -> Char array to hold data from Serial port
 * 
 * -> i2c address of slave device
 * -> 8 bit ints for data sent via i2c
 */
char command[16];

uint8_t RO_ADDRESS;
uint8_t regAdd;
uint8_t data;

String message;

void setup() {
  /*
   * initiliaze i2c commication as master
   * initialize Serial communication with baudrate Serial.begin(<baudrate>)
   * delay 500ms to let connections and possible setups to be established
   */
  message.reserve(32);
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
    /*
     * decode the received command and store different parts in variables
     * commands have structure: '<what to do>:<register>:<value>\n'
     * 
     */
    uint8_t pos1, pos2, pos3;
    String arg1, arg2, arg3;
    message = Serial.readStringUntil('\n');
    pos1 = message.indexOf(':',0);
    pos2 = message.indexOf(':', pos1+1);
    pos3 = message.indexOf(':', pos2+1);

    arg1 = message.substring(0,pos1);
    arg2 = message.substring(pos1+1,pos2);
    arg3 = message.substring(pos2+1,pos3);

    regAdd = arg2.toInt();
    data = arg3.toInt();

    Serial.println(arg1+"-"+arg2+"-"+arg3+"-");
    
    /*   
     *    Clear input buffer
     */
    while(Serial.available()){
      Serial.read();
    }

    /*
     * execute command i.e. read/write data, check connection or change i2c device address
     */
    if(arg1 == "T"){
      Wire.beginTransmission(RO_ADDRESS);
      _transErr = Wire.endTransmission();
      Serial.println(_transErr);
    }
    if(arg1 == "R"){
      Serial.println(readData(regAdd));
    }
    if(arg1 == "W"){
      Serial.println(writeData(regAdd, data));
    }
    if(arg1 == "A"){
      RO_ADDRESS = data;
      Serial.println(RO_ADDRESS);
    }
  }
  /*
   * delay 100µs between cycles
   */
  delayMicroseconds(100);
}
