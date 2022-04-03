#include <FreqCount.h>  // Actual freqency counting library

/*
Enables frequency determination by counting 5V logic pulses in fixed time window
*/


const char END = '\n';
const uint8_t END_PEEK = int(END); // Serial.peek returns byte as dtype int
const char DELIM = ':';
const char NULL_TERM = '\0';


size_t nProcessedBytes;
const size_t BUF_SIZE = 32;
char serialBuffer[BUF_SIZE]; // Max buffer 32 bytes in incoming serial data

// Commands
const char GATE_INTERVAL_CMD = 'G';
const char COUNTS_CMD = 'C';
const char FREQUENCY_CMD = 'F';
const char DELAY_CMD = 'D';
const char RESTART_CMD = 'R';


// Define vars potentially coming in from serial
uint16_t gateIntervalMillis = 1000; // Time window in which pulses are counted in ms
uint16_t serialDelayMillis = 1; // Delay between Serial.available() checks


float frequency(unsigned long counts, uint16_t sampling_time_ms){
  return (float)counts * 1000.0f / (float)sampling_time_ms;
}


void waitForResult(){
  while (!FreqCount.available()){
    delay(1);
  }
}

void restartCounter(){
  FreqCount.end();
  delay(1);
  FreqCount.begin(gateIntervalMillis);
}


void processIncoming(){

  // We have reached the end of the transmission; clear serial by calling read
  if (Serial.peek() == END_PEEK){
    Serial.read();
    serialBuffer[0] = NULL_TERM;
  }
  else {
    // Read to buffer until delimiter
    nProcessedBytes = Serial.readBytesUntil(DELIM, serialBuffer, BUF_SIZE);

    // Null-terminate string
    serialBuffer[nProcessedBytes] = NULL_TERM;
  }
}


void resetIncoming(){
  // Wait 500 ms and clear the incoming data
  delay(500);
  while(Serial.available()){
    Serial.read();
  }
}


void setup(){
  /*
   * initialize Serial communication with baudrate Serial.begin(<baudrate>)
   * delay 500ms to let connections and possible setups to be established
   * initiliaze FreqCounter
   */
  Serial.begin(115200);
  delay(500);  // Wait for Serial setup
  FreqCount.begin(gateIntervalMillis);
}


void loop() {

  if (Serial.available()){

    processIncoming();

    if (strlen(serialBuffer) == 1){

      // Lowercase means we want to set some value and print back that value on the serial bus
      if (isLowerCase(serialBuffer[0])){
        
        // Set sampling time millis
        if (toupper(serialBuffer[0]) == GATE_INTERVAL_CMD){
          processIncoming();
          gateIntervalMillis = atoi(serialBuffer);
          Serial.println(gateIntervalMillis);
          restartCounter();
        }

        // Set serial dealy in millis
        if (toupper(serialBuffer[0]) == DELAY_CMD){
          processIncoming();
          serialDelayMillis = atoi(serialBuffer);
          Serial.println(serialDelayMillis);
        }
      }

      // Here we want to read something or interact with the counter
      else {

        // Return sampling time millis
        if (serialBuffer[0] == GATE_INTERVAL_CMD){
          Serial.println(gateIntervalMillis);
        }

        // Read counts
        if (serialBuffer[0] == COUNTS_CMD){
          waitForResult();
          Serial.println(FreqCount.read());
        }

        // Read frequency
        if (serialBuffer[0] == FREQUENCY_CMD){
          waitForResult();
          Serial.println(frequency(FreqCount.read(), gateIntervalMillis), 2);
        }

        // Restart counter
        if (serialBuffer[0] == RESTART_CMD){
          restartCounter();
        }

        // Return serial delay millis
        if (serialBuffer[0] == DELAY_CMD){
          Serial.println(serialDelayMillis);
        }
      }

      // At this point command should have been processed
      // This last call to processIncoming should just remove the END char from serial buffer
      processIncoming();

    } else {
      Serial.println("error");
      resetIncoming();
    }
  }
  delay(serialDelayMillis);
}
