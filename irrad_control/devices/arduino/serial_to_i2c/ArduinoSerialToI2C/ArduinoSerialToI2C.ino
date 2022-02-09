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
    /*
     * decode the received command and store different parts in variables
     * commands have structure: '<what to do>:<register>:<value>\n'
     * 
     */
    size_t cmdlen = Serial.readBytesUntil('\n',command, 16);
    char cmd = command[0];
    
    regAdd = command[2]-'0';
    if(cmdlen>4){
      size_t dataLen = cmdlen - 4;
      char dataArr[dataLen];
      for(size_t c = 0; c < dataLen; c++){
        dataArr[c] = command[c+4];
      }
      data = atoi(dataArr);
    }

    /*   
     *    Clear input buffer
     */
    while(Serial.available()){
      Serial.read();
    }

    /*
     * execute command i.e. read/write data, check connection or change i2c device address
     */
    if(cmd == 'T'){
      Wire.beginTransmission(RO_ADDRESS);
      _transErr = Wire.endTransmission();
      Serial.println(_transErr);
    }
    if(cmd == 'R'){
      Serial.println(readData(regAdd));
    }
    if(cmd == 'W'){
      Serial.println(writeData(regAdd, data));
    }
    if(cmd == 'A'){
      RO_ADDRESS = data;
      Serial.println(RO_ADDRESS);
    }
  }
  /*
   * delay 100µs between cycles
   */
  delayMicroseconds(100);
}
