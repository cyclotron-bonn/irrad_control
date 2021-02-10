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
  char samplingtime = {'t'};
  long value = 10;
  long st;
  char cmd[6];
  int x;
  int k;
  int i;
  
  if(Serial.available()){
      for(k=0; k<=6; k++){
        cmd[k] = Serial.read();
        delay(100);
      }
      if(cmd[0] == setting){
        Serial.print('1');
        if(cmd[1] == samplingtime){
          Serial.println('3');
        }
      }
      else if(cmd[0] == getting){
        Serial.print('2');
        if(cmd[1] == samplingtime){
          Serial.print('3');
        }
      }
  }
 // if(FreqCount.available()){
 //   unsigned long count = FreqCount.read();
 //   Serial.println(count);
 // }
}


