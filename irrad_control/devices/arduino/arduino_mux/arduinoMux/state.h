#ifndef STATE
#define STATE

#include <SoftwareSerial.h>

#define BAUDRATE 9600
typedef unsigned int uint;

// holds globaly needed ressources
namespace state{
    const uint channel_count = 16;
    const uint buff_len = 256;

    const uint channels[channel_count] = {
        14, //CH11  //This is Pin A0
        15, //CH21  //This is Pin A1
        16, //CH31  //This is Pin A2
        17, //CH41  //This is Pin A3
        18, //CH51  //This is Pin A4
        19, //CH61  //This is Pin A5
        12, //CH71  //This is Pin D12
        13, //CH81  //This is Pin D13
        4,  //CH12  //This is Pin D4
        5,  //CH22  //This is Pin D5
        6,  //CH32  //This is Pin D6
        7,  //CH42  //This is Pin D7
        8,  //CH52  //This is Pin D8
        9,  //CH62  //This is Pin D9
        10, //CH72  //This is Pin D10
        11  //CH82  //This is Pin D11
    };

    const bool default_state[channel_count] = {
        false,
        false,
        false,
        false,
        false,
        false,
        false,
        false,
        false,
        false,
        false,
        true,
        true,
        false,
        true,
        false
    };

    const uint timeout_delay = 1500; // wait time before timing out and resetting in ms
    const char terminator = '\n'; // just use a null terminator as default i guess??
    const char enable_char = 'E';
    const char disable_char = 'D';
    const char hold_char = 'P';
    const char request_char = 'Q';
    const char reset_char = 'R';

    bool channel_state[channel_count]; // holds the current state of the pins
    char read_buffer[buff_len];
    bool changes_occured = false;


    #ifdef LEGACY // flag to use the old pins
    SoftwareSerial serial(2, 3);
    #else
    SoftwareSerial serial(0, 1);
    #endif
}

#endif
