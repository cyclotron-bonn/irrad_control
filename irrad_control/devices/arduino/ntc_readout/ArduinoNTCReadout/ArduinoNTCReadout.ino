/*
------------------------------------------------------------
Copyright (c) All rights reserved
SiLab, Institute of Physics, University of Bonn
-----------------------------------------------------------
Using the Arduino Nano as temperature sensor via voltage divider and NTC thermistor.
Every analog pin is connected to read the voltage over a thermistor, therefore up to 8
temperature values can be recorded.
*/

// Define resistance of thermistor at 25 degrees C
#define NTCNOMINAL 10000
// Nominal temperature for above resistance (almost always 25 C)
#define TEMPNOMINAL 25
// Average each temperature value over 10 analog readS
#define NSAMPLES 5
// The beta coefficient of the thermistor (usually 3000-4000); EPC B57891-M103 NTC Thermistor
#define BETACOEFF 3950
// Resistivity of the resistors in series to the NTC, forming voltage divider
#define RESISTOR 10000
// Kelvin
#define KELVIN 273.15
// Array of analog input pins on Arduino
const int THERMISTORPINS [] = {A0, A1, A2, A3, A4, A5, A6, A7};


// Setup
void setup(void) {
  // Initialize serial connection
  Serial.begin(115200);

  // Set 3.3V as external reference voltage instead of internal 5V reference
  analogReference(EXTERNAL);
}

// Steinhart-Hart equation for NTC: 1/T = 1/T_0 + 1/B * ln(R/R_0)
float steinhart_NTC(float r) {
  float temperature;

  // Do calculation
  temperature = 1.0 / (1.0 / (TEMPNOMINAL + KELVIN) + 1.0 / BETACOEFF * log(r / NTCNOMINAL));

  // To Kelvin
  temperature -= KELVIN;
  
  return temperature;
}

// Takes integer analog pin to read temperature from
float get_temp(int T_PIN) {

  // Store resitance value
  float ohm = 0;

  float temp_celsius;

  // take N samples in a row, with a slight delay
  for (int i=0; i< NSAMPLES; i++) {
    ohm += analogRead(T_PIN);
    delayMicroseconds(50);
  }

  // Do the average
  ohm /= NSAMPLES;

  // Convert  ADC resistance value to resistance in Ohm
  ohm = 1023 / ohm - 1 ;
  ohm = RESISTOR / ohm;

  temp_celsius = steinhart_NTC(ohm);

  return temp_celsius;
}

// Main loop
void loop(void) {
  // Needed variables
  char c;
  char delimiter = 'T';
  int temp_pin;
  float temp_celsius;

  // Get input from serial connection
  if (Serial.available()) {
    // Read from serial
    c = Serial.read();

    // If serial input c is delimiter, which is 'T', it is followed by integer pin number
    while (c == delimiter) {
      // Get pin number of analog pin from which temperature should be read
      temp_pin = Serial.parseInt();

      // We only have 8 analog pins
      if (0 <= temp_pin && temp_pin < 8) {
        // Get temperature as degrees Celsius
        temp_celsius = get_temp(THERMISTORPINS[temp_pin]);

        // Send out, two decimal places, wait
        Serial.println(temp_celsius, 2);
        delayMicroseconds(50);
      }
      else {
        // An Oooopsie happened
        Serial.println(999);
       }
      c = Serial.read();
    }
  }
}
