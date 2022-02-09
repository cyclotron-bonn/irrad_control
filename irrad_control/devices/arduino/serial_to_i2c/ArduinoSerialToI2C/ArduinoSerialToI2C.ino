#include <Wire.h> //i2c

uint8_t RO_ADDRESS = 0x20;

//Char array to hold data from Serial port
char command[8];

uint8_t regAdd;
uint8_t data;

void setup() {
  Wire.begin(); //initialize i2c communication as master
  Serial.begin(9600); //initialize Serial communication with baudrate 9600
 // regAddStr.reserve(32); //reserve memory for strings of size 32 bytes (should be enough for the communication)
 // dataStr.reserve(32); //is done to prevent memory
  delay(500);
  
}

uint8_t writeData(uint8_t _regAdd, uint8_t _data){
  Wire.beginTransmission(RO_ADDRESS); //begin transmission to R/O-Board with adress 0x20
  Wire.write(_regAdd); //transmit which register to write to
  Wire.write(_data); //send data
  //actually send the data, 
  return Wire.endTransmission(); //return errorcode
}

uint8_t readData(uint8_t _regAdd){
  Wire.beginTransmission(RO_ADDRESS);
  Wire.write(_regAdd);
  Wire.endTransmission();
  Wire.requestFrom(RO_ADDRESS, 0x1U); //request 1 byte (Unsigned) from Adress RO_ADDRESS
  return Wire.read();
}

void loop() {
  uint8_t _transErr;
  if(Serial.available()){
    size_t cmdlen = Serial.readBytesUntil('\n',command, 8);
    char cmd = command[0];
    if(cmdlen>1){
      size_t dataLen = cmdlen - 2;
      regAdd = command[1]-'0';
      char dataArr[dataLen];
      for(size_t c = 0; c < dataLen; c++){
        dataArr[c] = command[2+c];
      }
      data = atoi(dataArr);
    }
    //regAdd = regAddStr.toInt(); //convert to uint8_t
    //data = dataStr.toInt();
    while(Serial.available()){
      Serial.read(); //clear input buffer
    }
    if(cmd == 'T'){
      Wire.beginTransmission(RO_ADDRESS);
      _transErr = Wire.endTransmission();
      if(_transErr == 0){
        Serial.println("success");
      }
      else{
        Serial.println("noi2c");
      }
    }
    if(cmd == 'R'){
      Serial.println(readData(regAdd));
    }
    if(cmd == 'W'){
      Serial.println(writeData(regAdd, data));
    }
    if(cmd == 'A'){
      RO_ADDRESS = regAdd;
    }
  }
  delay(500);
}
