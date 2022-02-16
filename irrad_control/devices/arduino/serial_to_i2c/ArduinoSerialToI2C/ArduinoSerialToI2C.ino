#include <Wire.h> //i2c

/*
 * Initialize global variables and arrays
 * -> 8 bit i2c address of bus device
 * number of arguments to read
 * lenght of these arguments
 * (argnum x arglen)-array to hold all data
 * some chars for serial communication (argument seperator and end-character)
 */


uint8_t RO_ADDRESS;

const size_t argnum = 3;
const size_t arglen = 16;
char args[argnum][arglen];

const uint8_t _END = int('\n');
const char _DELIM = ':';
void setup() {
  /*
   * initiliaze i2c commication as master
   * initialize Serial communication with baudrate Serial.begin(<baudrate>)
   * delay 500ms to let connections and possible setups to be established
   */
  Wire.begin();
  Serial.begin(115200);
  delay(1000);
}


void receive(){
   /*
   * reads data from serial buffer and seperates at given _DELIM delimiter.
   * halts reading when _END character is found or args cant fit any more data (argnum)
   * empties serial buffer at the end
   */
    int peek;
    char curarg[arglen];
    size_t curarglen;
    size_t i = 0;
    do{
        curarglen = Serial.readBytesUntil(_DELIM, curarg, arglen);
        peek = Serial.peek();
        for(size_t j = 0; j<curarglen; j++){
          args[i][j] = curarg[j];
        }
        for(size_t j = curarglen; j<arglen; j++){
          args[i][j] = '\0';
        }
        i++;
    }while (i<argnum && peek != _END);
    resetInputBuffer();
}

void resetInputBuffer(void){
  /*
   * reads all data serial buffer and discharges them
   */
    while(Serial.available()){
        Serial.read();
    }
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
     * declare some constants and fill them according to their use
     */
    char command;
    uint8_t address;
    uint8_t data;
    receive();

    command = args[0][0];
    address = atoi(args[1]);
    data = atoi(args[2]);
    
    /*
     * execute command i.e. read/write data, check connection or change i2c device address
     */
    if(command == 'T'){
      Wire.beginTransmission(RO_ADDRESS);
      _transErr = Wire.endTransmission();
      Serial.print(_transErr);
      Serial.println(":");
    }
    if(command == 'R'){
      Serial.print(readData(address));
      Serial.println(":");
    }
    if(command == 'W'){
      writeData(address, data);
    }
    if(command == 'A'){
      RO_ADDRESS = address;
    }
    resetInputBuffer();
  }
  /*
   * delay 100µs between cycles
   */
  delayMicroseconds(1000);
}
