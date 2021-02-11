/* FreqCount - Example with serial output
 * http://www.pjrc.com/teensy/td_libs_FreqCount.html
 *
 * This example code is in the public domain.
 */

#include <FreqCount.h>

long samplingtime=1000;

void setup() {
  Serial.begin(9600);
  //st stands for smaplingtime and it starts with 1000
  FreqCount.begin(samplingtime);  
}

long get_Impuls() {
  unsigned long count;
  if(FreqCount.available()){
    FreqCount.begin(samplingtime);
    count = FreqCount.read();
    Serial.println(count);
  }
  return count;
}

void loop() {
  char setting = {'s'};
  char getting = {'g'};
  char time = {'t'};
  char impuls = {'i'};
  char cmd[7];
  int k;
  int i=0;
  int l = 2;
  int number[] = {};
  
  if(Serial.available()){
      for(k=0; k<=8; k++){
        cmd[k] = Serial.read();
        delay(100);
      }
      if(cmd[0] == setting){
        if(cmd[1] == time){
          while(cmd[l] == '0' || cmd[l] == '1' || cmd[l] == '2' || cmd[l] == '3' || cmd[l] == '4' || cmd[l] == '5' || cmd[l] == '6' || cmd[l] == '7' || cmd[l] == '8' || cmd[l] == '9'){
            number[i] = cmd[l] - '0';
            i = i + 1;
            l = l + 1;
          }
          Serial.println(number[0]);
          //Serial.print(number[1]);
          //Serial.println(number[2]);
          //delay(4000);
          samplingtime = 0;
          for(int j=0; j < i; j++){
            samplingtime = samplingtime*10;
            samplingtime = samplingtime + number[j];
          }
          Serial.println(samplingtime);
          FreqCount.begin(samplingtime);
        }
      }
      else if(cmd[0] == getting){
        if(cmd[1] == time){
          Serial.println(samplingtime);
        }
        else if(cmd[1] == impuls){
          get_Impuls();
        }
      }
  }
}


