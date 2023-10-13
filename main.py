#
# MicroPython-1.21.0-arm--with-newlib4.3.0 on RPi Pico W
#
from machine import Pin, mem32, Timer
from rp2 import PIO, StateMachine, asm_pio
from array import array
import binascii,time
import network, ntptime

# config in hodynyk_cfg.inf file
WL_SSID = 'YOUR WLAN SSID'
WL_PASSWD = 'YOUR WLAN PASSWD'
TZ_OFFSET = 7200

# read and exec the config for me (CODE INJECTION ALLOWED!!!)
with open( 'hodynyk_cfg.py' ) as fp:
    line = fp.read()
    while line:
        exec( line )
        line = fp.readline()
    fp.close()

#now for the display buffer DMA
DMA_BASE       = 0x50000000

DMA_CH0_NUM    = const(5)
DMA_CH0_BASE   = DMA_BASE + (0x040 * DMA_CH0_NUM)
CH0_READ_ADDR  = DMA_CH0_BASE+0x000
CH0_READ_ADDR_TRIG = DMA_CH0_BASE+0x03c
CH0_WRITE_ADDR = DMA_CH0_BASE+0x004
CH0_TRANS_COUNT= DMA_CH0_BASE+0x008
CH0_CTRL_TRIG  = DMA_CH0_BASE+0x00c
CH0_AL1_CTRL   = DMA_CH0_BASE+0x010

DMA_CH1_NUM    = const(6)
DMA_CH1_BASE   = DMA_BASE + (0x040 * DMA_CH1_NUM)
CH1_READ_ADDR  = DMA_CH1_BASE+0x000
CH1_READ_ADDR_TRIG = DMA_CH1_BASE+0x03c
CH1_WRITE_ADDR = DMA_CH1_BASE+0x004
CH1_TRANS_COUNT= DMA_CH1_BASE+0x008
CH1_CTRL_TRIG  = DMA_CH1_BASE+0x00c
CH1_AL1_CTRL   = DMA_CH1_BASE+0x010

PIO0_BASE      = 0x50200000
PIO0_BASE_TXF0 = PIO0_BASE+0x10

_p_ar=array('I',[0])				# global 1-element array 
@micropython.viper
def dispDmaStart(ar,nword):
    mem32[CH1_AL1_CTRL]=0
    mem32[CH0_AL1_CTRL]=0
    p=ptr32(ar)

    # control (reload) channel setup
    _p_ar[0]=p
    mem32[CH1_READ_ADDR]=ptr(_p_ar)
    mem32[CH1_WRITE_ADDR]=CH0_READ_ADDR
    mem32[CH1_TRANS_COUNT]=1
    IRQ_QUIET=0x1					# do not generate interrupt
    TREQ_SEL=0x3f					# no pacing (full speed / memory to memory)
    CHAIN_TO=DMA_CH0_NUM			# start data channel when done
    RING_SEL=0
    RING_SIZE=0						# no wrapping
    INCR_WRITE=0					# write to port
    INCR_READ=0						# read the same value
    DATA_SIZE=2						# 32-bit word transfer
    HIGH_PRIORITY=0
    EN=1
    CTRL1=(IRQ_QUIET<<21)|(TREQ_SEL<<15)|(CHAIN_TO<<11)|(RING_SEL<<10)|(RING_SIZE<<9)|(INCR_WRITE<<5)|(INCR_READ<<4)|(DATA_SIZE<<2)|(HIGH_PRIORITY<<1)|(EN<<0)
    mem32[CH1_AL1_CTRL]=CTRL1		# do not activate

    # data channel setup
    mem32[CH0_READ_ADDR]=p
    mem32[CH0_WRITE_ADDR]=PIO0_BASE_TXF0
    mem32[CH0_TRANS_COUNT]=nword
    IRQ_QUIET=0x1					# do not generate interrupt
    TREQ_SEL=0x00					# wait for PIO0_TX0
    CHAIN_TO=DMA_CH1_NUM			# start reload channel when done
    RING_SEL=0
    RING_SIZE=0						# no wrapping
    INCR_WRITE=0					# write to port
    INCR_READ=1						# read from array
    DATA_SIZE=2						# 32-bit word transfer
    HIGH_PRIORITY=0
    EN=1
    CTRL0=(IRQ_QUIET<<21)|(TREQ_SEL<<15)|(CHAIN_TO<<11)|(RING_SEL<<10)|(RING_SIZE<<9)|(INCR_WRITE<<5)|(INCR_READ<<4)|(DATA_SIZE<<2)|(HIGH_PRIORITY<<1)|(EN<<0)
    mem32[CH0_CTRL_TRIG]=CTRL0		# activate

# now for the display parallel 8*8 multiplex interface
@asm_pio(
    out_init= [PIO.OUT_LOW] * 16
    , out_shiftdir=PIO.SHIFT_LEFT
    , autopull=True, pull_thresh=32
    )
def disp_pio():
    out(pins,16)

# create he display buffer, fill initial values
ndisp=8								# number of digits
bdisp=array("B",[0]*ndisp*2)		# two bytes per digit: value and position
for i in range(ndisp):				# me no cares about output digit order when collating halfwords into words as position is put out too
    bdisp[ i * 2 ] = 0x80			# '.' - segment driver lines
    bdisp[ i * 2 + 1 ] = (0x1 << i)	# digit driver line for the digit position

# now start the display refresh
dispDmaStart(bdisp,int(ndisp/2))	# configure infinite DMA bdisp wodrs buffer transfer
sm=StateMachine(0,disp_pio,out_base=Pin(6),freq=2000)		# construct the PIO driver
sm.active(1)						# activate
sm.put(0)							# kick SM DREQ stall after soft reboot

# now connect to lan
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
network.hostname('PiCow-' + str(binascii.hexlify(wlan.config('mac')))[8:-1] )
wlan.connect(WL_SSID, WL_PASSWD)

i=0
while not wlan.isconnected():
    bdisp[ i * 2 ] ^= 0xbc			# 'C.'
    i = (i + 1 ) & 7
    time.sleep(1)
bdisp[ i * 2 ] = 0x5c				# 't'

#print("Local time before synchronization：%s" %str(time.localtime()))
ntptime.settime()
#print("Local time after synchronization：%s" %str(time.localtime()))

# now the font for digits
D7SEG=(0x3f, 0x03, 0x6d, 0x67, 0x53, 0x76, 0x7e, 0x23, 0x7f, 0x77	# 0-9
       , 0x7b, 0x5e, 0x4c, 0x4f, 0x7c, 0x78 )						# AbcdEF

#now for dislaying local time
def updBufTime(timer):
    t=time.localtime( time.time() + TZ_OFFSET )
    #t=time.localtime( )
    bdisp[0] = D7SEG[ t[3] // 10 ]
    bdisp[2] = D7SEG[ t[3] % 10 ]
    bdisp[4] = 0x0
    bdisp[6] = D7SEG[ t[4] // 10 ]
    bdisp[8] = D7SEG[ t[4] % 10 ]
    bdisp[10] = 0x0
    bdisp[12] = D7SEG[ t[5] // 10 ]
    bdisp[14] = D7SEG[ t[5] % 10 ]

timr = Timer(period=1000, mode=Timer.PERIODIC, callback=updBufTime )
