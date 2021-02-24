/* FreqCount - Example with serial output
 * http://www.pjrc.com/teensy/td_libs_FreqCount.html
 *
 * This example code is in the public domain.
 */

#include <FreqCount.h>

void setup() {
  Serial.begin(9600);
  FreqCount.begin(1000);
}

void loop() {
  char setting = {'s'};
  char getting = {'g'};
  char number = {'4'};
  char time = {'t'};
  // st stands for samplingTime
  long st;
  char cmd;
  int i;
  //char gst = {'20'};
  
  while(Serial.available()){
    cmd = Serial.read();
    Serial.print(cmd);
  }
  if(Serial.available()){
    Serial.print(i);
  }
    //while(cmd == setting){
    //  st = Serial.parseInt();
    //  Serial.println(st);
    //  cmd = Serial.read();
    //}
    
    //while(cmd == getting){
    //  Serial.println('2');
    //  cmd = Serial.read();
    //}
    
 //   if(cmd != setting || cmd != getting){
      // A mistake happend
 //     Serial.println('0');
 //   } 
 // if(FreqCount.available()){
 //   unsigned long count = FreqCount.read();
 //   Serial.println(count);
 // }
}


