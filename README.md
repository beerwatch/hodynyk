So, you want to drive an 8-digit 7-segment display? Do you think you need a MAX7219 LED driver chip? 

No, you don't.

Just use RP2040 PIO and some DMA for the same result. Well, you'll need some transistor driver arrays, like ULN2803 (lower) and TD62783 (upper) or similar, for driving the multiplex wires. 

See how to use RPI2040W for the task right here.

Outputs from GPIO6 to GPIO13 are driving digit segments (a, b, c, d, e, f, g, dp), outputs from GPI14 to GPIO21 are driving individual digits (leftmost to rughtmost).

The program uses chained DMA to scan the digits and PIO to output the 16 bit halfwords driving both segments and scan line at the same time. It connects to WiFi and gets initial NTP time. Display updates are driven via periodic timer. 

You have to upload your own WiFi and TZ configuration via MicroPython REPL. There are no additional controls and outputs at the moment. I plan to add a button, buzzer and alarm calendar from Budiq, my other Pythn project later.
