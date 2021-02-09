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
  long value;
  long st;
  char cmd;
  char gst = {'20'};
  
  if(Serial.available()){
    cmd = Serial.read();
    
    while(cmd == setting){
      Serial.println('1');
      st = Serial.parseInt();
      Serial.println(st);
      cmd = Serial.read();
    }
    while(cmd == getting){
      Serial.println('2');
      Serial.print(gst);
      cmd = Serial.read();
    }
    if(cmd != setting || cmd != getting){
      // A mistake happend
      Serial.println('0');
    }
  }
  if(FreqCount.available()){
    unsigned long count = FreqCount.read();
    Serial.println(count);
  }
}


