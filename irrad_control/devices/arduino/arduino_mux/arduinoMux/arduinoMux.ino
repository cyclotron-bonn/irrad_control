#include "state.h"

// function pointer pointing to zero
// thus jumping to the beginning of the bootloader
void (*reset) (void) = 0;


void reset_in(int ms) {
    state::serial.println("called reset");
    delay(ms);
    reset();
}


// go to the default state if no input or ping is received
void dead_state() {
    for (uint c = 0; c < state::channel_count; ++c) {
        digitalWrite(state::channels[c], state::default_state[c]);
    }    
}


void output_pin_state() {
    // writes the current pin states to the ouputs
    for (uint c = 0; c < state::channel_count; ++c) {
        digitalWrite(state::channels[c], state::channel_state[c]);
    }

    state::changes_occured = false;
}


//parses the read buffer and 
// returns zero on success or numerical error code on failure
int parse(uint read_size) {
    int cmd_c;
    // todo: skip garbage chars at the beginning (if for example serial buffer was not empty to start with)
    if (state::read_buffer[0] == state::hold_char) {
        return 0; // no error but also don't do anything
    }

    if (state::read_buffer[0] == state::request_char) {
        for (uint i = 0; i < state::channel_count; ++i) {
            state::serial.print(state::channel_state[i]);
            state::serial.print(' ');
        }
        state::serial.print('\n');
        return 0;
    }

    if (state::read_buffer[0] == state::enable_char) {
        cmd_c = atoi(state::read_buffer + 1);
        if (cmd_c < 0 || cmd_c >= state::channel_count) {
            return 1;
        }
        state::channel_state[cmd_c] = true;
        state::changes_occured = true;
        return 0;
    }

    if (state::read_buffer[0] == state::disable_char) {
        cmd_c = atoi(state::read_buffer + 1);
        if (cmd_c < 0 || cmd_c >= state::channel_count) {
            return 1;
        }
        state::channel_state[cmd_c] = false;
        state::changes_occured = true;
        return 0;
    }

    if(state::read_buffer[0] == state::reset_char) {
        cmd_c = atoi(state::read_buffer + 1);
        reset_in(cmd_c);
    }

    return 1; // did evidently not parse succesfully
}


void clear_read_buffer() {
    for (uint i = 0; i < state::buff_len; ++ i)
        state::read_buffer[i] = '\0';
}


void setup() {
    // initialiize pins
    for (uint c = 0; c < state::channel_count; ++c) {
        pinMode(state::channels[c], OUTPUT);
        state::channel_state[c] = state::default_state[c];
    }
    dead_state();

    // initialize serial connection
    state::serial.setTimeout(state::timeout_delay);
    state::serial.begin(BAUDRATE);
}


void loop() {
    clear_read_buffer();
    uint read_len = state::serial.readBytesUntil(state::terminator, state::read_buffer, state::buff_len);

    if (!read_len) dead_state(); // read_len being zero implies no data received in the timeout time
    
    // should it shut down on invalid data or just wait for valid data??
    else if (parse(read_len)) dead_state(); // a parse failure implies invalid data in the received
    else if (state::changes_occured) output_pin_state();
}
